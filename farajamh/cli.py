from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path

from .common import canonical, config, require, resolve, validate
from .exports import export_sssom, review_package, validate_catalog, validate_sssom
from .pilot import deny_network, dry_run
from .pipeline import App
from .reporting import report, scorecard
from .terminology import import_owl, import_rf2


def parser():
    p = argparse.ArgumentParser(description="FarajaMH synthetic-only research prototype")
    p.add_argument("--config", default="config.yaml")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Initialize persistent SQLite storage")
    sub.add_parser("preflight", help="Report required terminology prerequisites; no model downloads")
    run = sub.add_parser("run", help="Process one synthetic JSON record; ends awaiting human review")
    run.add_argument("input", type=Path)
    run.add_argument("--model-set", help="Model set from model_profiles (default: the configured model_profile)")
    batch = sub.add_parser("batch")
    batch.add_argument("input", type=Path)
    batch.add_argument("--manifest", type=Path, required=True)
    batch.add_argument("--model-set")
    for name in ("review", "adjudicate", "curate", "mapping-review", "add-evidence"):
        cmd = sub.add_parser(name)
        cmd.add_argument("utterance_id", nargs="?" if name == "review" else None)
        cmd.add_argument("--decision", type=Path)
        cmd.add_argument("--version", type=int)
        cmd.add_argument("--token-env", default="FARAJA_SESSION_TOKEN")
        if name == "review":
            cmd.add_argument("--serve", action="store_true")
            cmd.add_argument("--port", type=int, default=8765)
            cmd.add_argument("--export-package", type=Path)
    imp = sub.add_parser("import-terminology")
    imp.add_argument("resource", choices=("MFOEM", "MFOMD", "SNOMED_CT"))
    imp.add_argument("--index", type=Path, required=True)
    imp.add_argument("--owl", type=Path)
    imp.add_argument("--concepts", type=Path)
    imp.add_argument("--descriptions", type=Path)
    imp.add_argument("--language", type=Path)
    imp.add_argument("--edition")
    imp.add_argument("--release", required=True)
    imp.add_argument("--refset")
    export = sub.add_parser("export-sssom")
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--token-env", default="FARAJA_SESSION_TOKEN")
    export.add_argument("--demonstration", action="store_true")
    for name in ("report", "dry-run"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--out", type=Path, required=True)
    sub.choices["report"].add_argument("--include-flagged", action="store_true",
        help="Include cases marked as test or withdrawn")
    sub.add_parser("scorecard", help="Each model against reviewer-approved meanings (synthetic cases only)")
    intake = sub.add_parser("intake", help="Check, then run, a CSV or JSONL file of synthetic cases using the review screen's fields")
    intake.add_argument("input", type=Path)
    intake.add_argument("--token-env", default="FARAJA_SESSION_TOKEN")
    intake.add_argument("--model-set")
    store = sub.add_parser("set-token", help="Store a salted hash of an identity's token in SQLite")
    store.add_argument("identity")
    store.add_argument("--token-env", help="Read the token from this variable (default: the identity's configured token_env); prompts if unset")
    check = sub.add_parser("validate")
    check.add_argument("kind", choices=("sssom", "catalog"))
    check.add_argument("file", type=Path)
    return p


def execute(args, cfg):
    if args.command == "dry-run":
        return dry_run(cfg, args.out.resolve())
    if args.command == "validate":
        return (validate_sssom if args.kind == "sssom" else validate_catalog)(args.file)
    if args.command == "review" and args.serve:
        from .webapp import server
        print(f"Review application: http://127.0.0.1:{args.port} · configured tokens required", flush=True)
        server(cfg, args.port).serve_forever()
        return {}
    if args.command == "import-terminology":
        if args.resource == "SNOMED_CT":
            require(all((args.concepts, args.descriptions, args.language, args.edition, args.refset)), "RF2 concepts/descriptions/language/edition/refset required")
            return import_rf2(args.index, args.concepts, args.descriptions, args.language, args.edition, args.release, args.refset)
        require(args.owl, "Local OWL file required")
        return import_owl(args.index, args.owl, args.resource, args.release)
    app = App(cfg)
    try:
        if args.command == "init": return {"storage": str(resolve(cfg, cfg["storage"])), "mode": cfg["mode"]}
        if args.command == "preflight":
            results = app.resolver.all(["emotional pain"])
            return {"terminology": results, "ready": all(r["state"] in ("HITS", "NO_RESULTS") for r in results.values()),
                    "model_calls": "NOT EXECUTED; model availability checked during run"}
        if args.command == "run":
            d = app.run(json.loads(args.input.read_text()), profile=args.model_set)
            return {"utterance_id": d["source"]["utterance_id"], "version": d["version"], "state": d["state"], "comparison": d["comparison"]["state"]}
        if args.command == "batch":
            manifest = json.loads(args.manifest.read_text())
            validate("manifest", manifest)
            records = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
            require(len(records) == manifest["count"], "Manifest count mismatch")
            # Validate all inputs before first model call/write.
            for source in records: validate("source", source)
            results = [app.run(source, profile=args.model_set) for source in records]
            return {"count": len(results), "states": [d["state"] for d in results]}
        if args.command == "report": return report(app, args.out, args.include_flagged)
        if args.command == "scorecard": return scorecard(app.store.all(), cfg["model_profiles"])
        if args.command == "set-token":
            profile = cfg["identities"].get(args.identity)
            require(profile is not None, "Unknown identity")
            secret = os.environ.get(args.token_env or profile["token_env"], "") or getpass.getpass(f"Token for {args.identity}: ")
            app.store.set_credential(args.identity, secret)
            return {"identity": args.identity, "stored": "scrypt hash", "storage": str(resolve(cfg, cfg["storage"]))}
        token = os.environ.get(args.token_env, "")
        if args.command == "intake":
            from .intake import run_file
            return run_file(app, args.input, token, args.model_set)
        if args.command == "export-sssom": return export_sssom(app, args.out, token, args.demonstration)
        if args.command == "review" and args.export_package:
            return review_package(app, args.utterance_id, args.export_package, token)
        require(args.decision and args.version is not None and args.utterance_id, "Decision file, utterance ID and exact --version required")
        operation = {"mapping-review": "mapping", "add-evidence": "add_evidence"}.get(args.command, args.command)
        d = getattr(app, operation)(args.utterance_id, json.loads(args.decision.read_text()), token, args.version)
        return {"utterance_id": d["source"]["utterance_id"], "version": d["version"], "state": d["state"]}
    finally:
        app.store.db.close()


def main():
    args = parser().parse_args()
    try:
        cfg = config(args.config)
        # Review HTTP server must accept loopback requests; its outbound gateway remains fixture-blocked.
        if cfg["mode"] == "fixture" and not (args.command == "review" and args.serve):
            with deny_network(): result = execute(args, cfg)
        else: result = execute(args, cfg)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "preflight" and not result["ready"]: raise SystemExit(2)
    except (ValueError, KeyError, OSError, __import__("jsonschema").ValidationError) as exc:
        print(canonical({"error": str(exc)[:1000], "type": type(exc).__name__}))
        raise SystemExit(2)


if __name__ == "__main__": main()
