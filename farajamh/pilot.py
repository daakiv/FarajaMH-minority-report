"""Explicit simulated approval driver. Only callable in fixture mode; never creates human evidence."""
from __future__ import annotations

import copy
import json
import os
import secrets
import socket
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from .common import digest, require, resolve, validate, write_json
from .exports import export_sssom, review_package
from .pipeline import App, applicability
from .reporting import report


@contextmanager
def deny_network():
    def blocked(*args, **kwargs): raise RuntimeError("OFFLINE DRY-RUN: socket network blocked")
    with patch.object(socket.socket, "connect", blocked), patch.object(socket.socket, "connect_ex", blocked), patch("socket.create_connection", blocked), patch("socket.getaddrinfo", blocked):
        yield


def simulate(app: App, records: list[dict], out: Path):
    require(app.cfg["mode"] == "fixture", "Simulation prohibited outside fixture mode")
    profiles = app.cfg["identities"]
    required = ("demo_ke", "demo_tz", "demo_arbitrator", "demo_curator")
    require(all(profiles[x]["simulated"] for x in required), "Demo accounts must be explicitly simulated")
    tokens = {x: secrets.token_urlsafe(32) for x in required}
    environment = {profiles[x]["token_env"]: tokens[x] for x in required}
    decisions = []
    with patch.dict(os.environ, environment):
        for i, source in enumerate(records, 1):
            d = app.run(source)
            uid = source["utterance_id"]
            groups = d["comparison"]["groups"]
            first = copy.deepcopy(groups[0]["hypotheses"][0]["hypothesis"])
            last = copy.deepcopy(groups[-1]["hypotheses"][0]["hypothesis"])
            for identity, h in (("demo_ke", first), ("demo_tz", last)):
                payload = {"action": "minority" if identity == "demo_tz" and d["comparison"]["majority_group"] and len(groups) > 1 else "accept",
                    "preferred": [h], "comment": "SIMULATED independent submission for software testing only",
                    "evidence_refs": ["E1"], "uncertainties": ["Cultural validity NOT MEASURED"], "risk_signal": "not_flagged", "applicability_confirmed": False}
                d = app.review(uid, payload, tokens[identity], d["version"])
                decisions.append({"utterance_id": uid, "actor": identity, "simulated": True, "decision": payload})
            meanings = [last if i == 2 else first]
            action = "approve"
            if i == 1:
                first["id"], last["id"] = "emotional", "somatic"
                meanings, action = [first, last], "multiple"
            if i == 3: meanings, action = [], "unresolved"
            if i == 17: meanings, action = [], "request_context"
            payload = {"action": action, "meanings": meanings,
                "rationale": "SIMULATED adjudication; competing readings in the burning-heart example are illustrative, not cultural facts.",
                "evidence_refs": ["E1"], "risk_signal": "not_flagged"}
            d = app.adjudicate(uid, payload, tokens["demo_arbitrator"], d["version"])
            decisions.append({"utterance_id": uid, "actor": "demo_arbitrator", "simulated": True, "decision": payload})
            if i in (1, 2, 4):
                for h in meanings:
                    sense_id = "FARAJA:demo-" + digest(h["semantic_frame"])[:12]
                    payload = {"sense_id": sense_id, "meaning_id": h["id"], "source_label": source["original_text"],
                        "english_gloss": h["meaning"], "definition": "SIMULATED contextual sense: " + h["meaning"],
                        "synonyms": [], "cultural_applicability": "Constructed context only; not validated community usage",
                        "example_refs": [uid], "evidence_refs": ["E1"], "owner": "SIMULATED research curator",
                        "reuse_approved": True, "applicability": applicability(source)}
                    d = app.curate(uid, payload, tokens["demo_curator"], d["version"])
                    decisions.append({"utterance_id": uid, "actor": "demo_curator", "simulated": True, "decision": payload})
                    for resource, lookup in d["terminology"].items():
                        # P01 emotional sense gets three fictitious mappings; other senses retain scoped gaps.
                        candidate = lookup["candidates"][0] if lookup["candidates"] and i == 1 and h["id"] == "emotional" else None
                        payload = {"resource": resource, "action": "approve" if candidate else "gap", "sense_id": sense_id,
                            "candidate_id": candidate["id"] if candidate else None, "predicate": "skos:relatedMatch" if candidate else None,
                            "rationale": "SIMULATED fit decision against fictional release only; no real terminology verification",
                            "evidence_refs": ["E1"]}
                        d = app.mapping(uid, payload, tokens["demo_curator"], d["version"])
                        decisions.append({"utterance_id": uid, "actor": "demo_curator", "simulated": True, "decision": payload})
            if i == 1:
                review_package(app, uid, out / "review-package", tokens["demo_arbitrator"])
        write_json(out / "SIMULATED-decisions.json", decisions)
        result = export_sssom(app, out / "SIMULATED-artifacts", tokens["demo_curator"], demonstration=True)
    return result


def dry_run(cfg: dict, out: Path) -> dict:
    require(cfg["mode"] == "fixture", "dry-run requires fixture configuration")
    require(not out.exists(), "Use a new pilot output directory to preserve prior evidence")
    out.mkdir(parents=True)
    cfg = copy.deepcopy(cfg)
    cfg["storage"] = str((out / "pilot.sqlite").resolve())
    manifest = json.loads(resolve(cfg, "pilot/manifest.json").read_text())
    validate("manifest", manifest)
    records = [json.loads(line) for line in resolve(cfg, "pilot/" + manifest["dataset"]).read_text().splitlines()]
    require(len(records) == manifest["count"], "Manifest count mismatch")
    with deny_network():
        app = App(cfg)
        exported = simulate(app, records, out)
        metrics = report(app, out / "report")
        app.store.db.close()
    write_json(out / "run-manifest.json", {"synthetic": True, "simulated": True, "network_blocked": True,
        "fixture_manifest": manifest, "configuration": cfg, "export": exported})
    return {"directory": str(out), "utterances": metrics["utterances"], "model_counts": metrics["model_counts"],
        "agreement_states": metrics["agreement_states"], "real_reviewer_metrics": metrics["real_reviewer_metrics"]}
