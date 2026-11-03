"""One outbound gateway. Fixture execution forbids requests, even to localhost."""
import json
import urllib.request
from urllib.parse import urlparse

from .common import require


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused: endpoints must be explicitly configured")


def request(cfg: dict, url: str, payload=None, token: str | None = None) -> dict:
    require(cfg["mode"] != "fixture", "OFFLINE: network blocked")
    parsed = urlparse(url)
    require(not parsed.username and not parsed.password and not parsed.fragment, "Credentials/fragments forbidden in endpoint")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    require(origin in cfg["network"]["allowed_origins"], "Endpoint not allowlisted")
    require(parsed.scheme == "https" or parsed.hostname in ("127.0.0.1", "localhost", "::1"), "Non-loopback endpoints require TLS")
    if cfg["mode"] == "local":
        require(parsed.hostname in ("localhost", "127.0.0.1", "::1"), "Local mode only permits loopback")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    # Never log URLs with server messages or credential-bearing exceptions.
    with urllib.request.build_opener(NoRedirect).open(req, timeout=cfg["network"]["timeout_seconds"]) as response:
        return json.load(response)
