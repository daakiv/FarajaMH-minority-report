from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).parent
CATEGORY_FAMILIES = json.loads((ROOT / "resources/categories.json").read_text())
RESOURCES = ("MFOEM", "MFOMD", "SNOMED_CT")
SPELLING_HINTS = {h["written"].casefold(): h for h in json.loads((ROOT / "resources/spelling_hints.json").read_text())}


def spelling_hints(text: str) -> list[dict]:
    """Display-only hints for listed spelling variants. The original text is never changed."""
    found = {}
    for match in re.finditer(r"\w+", text):
        hint = SPELLING_HINTS.get(match.group().casefold())
        if hint and match.group().casefold() not in found:
            found[match.group().casefold()] = {**hint, "written": match.group(), "start": match.start(), "end": match.end()}
    return list(found.values())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path: Path) -> str:
    # Upstream compute_sha256 streaming pattern; errors now propagate, never 'UNREADABLE'.
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def validate(name: str, data: Any) -> None:
    schema = json.loads((ROOT / "schemas" / f"{name}.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(data)


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ValueError(message)


def config(path: str | Path) -> dict:
    path = Path(path).resolve()
    cfg = yaml.safe_load(path.read_text())
    require(cfg["mode"] in ("fixture", "local", "connected"), "Invalid execution mode")
    require(set(cfg["terminology"]) == set(RESOURCES), "All three required resources must be configured")
    require(all(cfg["terminology"][r]["enabled"] for r in RESOURCES), "Required terminology cannot be disabled")
    # Named model sets (e.g. small local, large hosted). A plain `models:` list is one set called "default".
    require(not ("models" in cfg and "model_profiles" in cfg), "Use either models or model_profiles, not both")
    profiles = cfg.get("model_profiles") or {"default": {"label": "Configured models", "models": cfg.get("models", [])}}
    for name, profile in profiles.items():
        require(re.fullmatch(r"[a-z0-9_-]+", name), "Model set names use lowercase letters, digits, - or _")
        models = profile["models"]
        require(len(models) >= 3 and len({m["id"] for m in models}) == len(models), f"Model set {name}: select at least three distinct configurations")
        require(len({digest({k: v for k, v in m.items() if k != "id"}) for m in models}) == len(models), f"Model set {name}: duplicate model configurations")
        # Hosted means the utterance is sent off this machine (an API, or an Ollama cloud model).
        profile["hosted"] = any(m["provider"] == "openai_compatible" or str(m.get("model", "")).endswith("-cloud") for m in models)
        profile.setdefault("label", name)
    cfg["model_profiles"] = profiles
    cfg.setdefault("model_profile", next(iter(profiles)))
    require(cfg["model_profile"] in profiles, "model_profile must name one of model_profiles")
    cfg["models"] = profiles[cfg["model_profile"]]["models"]
    require(cfg["voting"]["minimum_primary_votes"] >= 3, "Minimum participation cannot be below three")
    require(cfg["review"]["minimum_reviewers"] >= 1, "Human review required")
    require(cfg["review"].get("workflow", "legacy") in ("legacy", "single_reviewer"), "Unknown review workflow")
    require(cfg["review"]["ckb_requires_arbitration"] is True, "This prototype requires arbitration for CKB reuse as well")
    rate = cfg["review"].get("agreed_sample_rate")
    require(rate is None or (isinstance(rate, (int, float)) and 0 <= rate <= 1), "agreed_sample_rate must be between 0 and 1")
    require(rate is None or isinstance(cfg["review"].get("agreed_sample_seed"), str) and cfg["review"]["agreed_sample_seed"].strip(),
        "Set agreed_sample_seed so the review sample can be reproduced")
    require({"flagged", "uncertain"} <= set(cfg["risk"]["priority_signals"]), "Flagged and uncertain risk must enter PRIORITY")
    require(cfg["voting"]["grouping_version"] == "semantic-frame-conservative-v1", "Unsupported grouping procedure version")
    for identity, person in cfg["identities"].items():
        require(re.fullmatch(r"[A-Za-z0-9_-]+", identity), "Invalid identity")
        require(not ({"reviewer", "arbitrator"} <= set(person["roles"])), "Reviewer and arbitrator identities must be distinct")
        require(person.get("expertise") and person.get("locality_familiarity"), "Record declared expertise and familiarity")
        require(re.fullmatch(r"FARAJA_[A-Z0-9_]+", person["token_env"]), "Use a dedicated credential environment variable")
    cfg["_base"] = str(path.parent)
    return cfg


def resolve(cfg: dict, path: str) -> Path:
    return (Path(cfg["_base"]) / os.path.expandvars(path)).resolve()


def scan_identifiers(value: Any) -> None:
    text = canonical(value)
    require(not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\d)(?:\+?254|\+?255)\d{9}(?!\d)", text),
            "Possible email or East African phone identifier: remove from synthetic input")


def evidence_check(refs: list[str], source: dict) -> None:
    allowed = {e["id"] for e in source["evidence"]}
    require(set(refs) <= allowed, "Evidence reference not in authorized source evidence")


def code_hash() -> str:
    return digest({str(p.relative_to(ROOT)): file_hash(p) for p in sorted(ROOT.rglob("*"))
                   if p.is_file() and p.suffix in (".py", ".json", ".md", ".html")})
