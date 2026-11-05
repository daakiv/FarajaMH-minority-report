"""Loopback-only persistent review UI. Authenticated mutations call the same backend as the CLI."""
import io
import json
import re
import zipfile
from jsonschema import ValidationError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .common import CATEGORY_FAMILIES, ROOT, canonical, require, spelling_hints
from .pipeline import App
from .workflow import progress
from .jobs import Runs, ReviewJobs, export_root, model_availability
from .intake import IntakeError
from .exports import export_overview, export_readiness
from .reporting import scorecard


def server(cfg: dict, port: int = 8765):
    runs = Runs(cfg)
    review_jobs = ReviewJobs(cfg)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No credentials, source text, URLs or submitted evidence in access logs.

        def send(self, code, body, content_type="application/json", filename=None):
            encoded = body if isinstance(body, bytes) else body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type if filename else content_type + "; charset=utf-8")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(encoded)

        def handle_request(self, mutate=False):
            app = None
            try:
                require(self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"), "Invalid Host")
                if self.headers.get("Origin"):
                    require(self.headers["Origin"] in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"), "Cross-origin request blocked")
                path = urlparse(self.path).path
                if not mutate and path == "/":
                    return self.send(200, (ROOT / "templates/review.html").read_text(), "text/html")
                token = self.headers.get("Authorization", "").removeprefix("Bearer ")
                app = App(cfg)
                person = app.identity(token)
                if not mutate and path == "/api/queue":
                    result = {"identity": person, "mode": cfg["mode"], "suggested_id": runs.next_id(app), "categories": CATEGORY_FAMILIES, "workflow": cfg["review"].get("workflow", "legacy"),
                        "model_sets": [{"name": n, "label": p["label"], "hosted": p["hosted"], "models": [m["id"] for m in p["models"]]} for n, p in cfg["model_profiles"].items()],
                        "model_set_default": cfg["model_profile"], "items": [{"id": d["source"]["utterance_id"], "state": d["state"],
                        "priority": d["priority"]["queue"], "version": d["version"],
                        "flag": (d.get("case_flag") or {}).get("status", "active"), "next_task": progress(d)["next_task"], "model_set": (d.get("model_set") or {}).get("name")} for d in app.store.all()]}
                elif not mutate and path == "/api/scorecard":
                    result = scorecard(app.store.all(), cfg["model_profiles"])
                elif not mutate and path == "/api/models":
                    result = model_availability(cfg)
                elif not mutate and path == "/api/exports":
                    result = export_overview(app, person, demonstration=cfg["mode"] == "fixture")
                elif not mutate and path.startswith("/api/export-package/"):
                    app.identity(token, "terminology")
                    name = path.rsplit("/", 1)[1].removesuffix(".zip")
                    # Only dated package folders written by the export job can be downloaded.
                    folder = export_root(cfg) / name
                    require(re.fullmatch(r"\d{8}T\d{6}Z", name) and folder.is_dir(), "Unknown export package")
                    buffer = io.BytesIO()
                    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                        for file in sorted(folder.iterdir()):
                            archive.write(file, f"farajamh-export-{name}/{file.name}")
                    return self.send(200, buffer.getvalue(), "application/zip", f"farajamh-export-{name}.zip")
                elif not mutate and path.startswith("/api/review-job/"):
                    result = review_jobs.get(path.rsplit("/", 1)[1], person)
                elif not mutate and path.startswith("/api/run/"):
                    result = runs.get(path.rsplit("/", 1)[1], person)
                elif not mutate and path.startswith("/api/dossier/"):
                    result = app.view(path.rsplit("/", 1)[1], token)
                    result["export_readiness"] = export_readiness(app, result, person, demonstration=cfg["mode"] == "fixture")
                    result["spelling_hints"] = spelling_hints(result["source"]["original_text"])
                elif mutate and path.startswith("/api/"):
                    require(self.headers.get("Content-Type") == "application/json", "JSON content type required")
                    size = int(self.headers.get("Content-Length", "0"))
                    require(0 < size <= 1000000, "Invalid request size")
                    body = json.loads(self.rfile.read(size))
                    operation = path.removeprefix("/api/")
                    if operation == "intake":
                        result = runs.start(app, body, app.identity(token, "reviewer"))
                        return self.send(202, canonical(result))
                    if operation == "background/export":
                        return self.send(202, canonical(review_jobs.start_export(app, token)))
                    if operation.startswith("background/"):
                        result = review_jobs.start(app, operation.split("/",1)[1], body, token)
                        return self.send(202, canonical(result))
                    require(operation in ("signoff", "review", "adjudicate", "complete_review", "refresh_terminology", "run_expression", "curate", "mapping", "add_evidence", "flag_case"), "Unknown action")
                    result = getattr(app, operation)(body["utterance_id"], body["decision"], token, body["version"])
                else:
                    return self.send(404, canonical({"error": "Not found"}))
                self.send(200, canonical(result))
            except Exception as exc:
                # Backend validation errors are safe; don't return server/request credential details.
                field = getattr(exc, "field", None)
                if isinstance(exc, ValidationError):
                    parts = [str(p) for p in exc.absolute_path]
                    if exc.validator == "required" and isinstance(exc.instance, dict):
                        missing = [key for key in exc.validator_value if key not in exc.instance]
                        if missing: parts.append(missing[0])
                    field = ".".join(parts) or "Submission"
                    message = f"Check {field}: {exc.message}"[:500]
                else:
                    message = str(exc)[:500] if isinstance(exc, (ValueError, KeyError)) else type(exc).__name__
                self.send(400, canonical({"error": message, "field": field}))
            finally:
                if app:
                    app.store.db.close()

        def do_GET(self): self.handle_request()
        def do_POST(self): self.handle_request(True)
    class Server(ThreadingHTTPServer):
        def server_close(self):
            super().server_close()
            runs.pool.shutdown(wait=True)
            review_jobs.pool.shutdown(wait=True)
    return Server(("127.0.0.1", port), Handler)
