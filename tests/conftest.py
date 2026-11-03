import copy
import json
from pathlib import Path

import pytest

from farajamh.common import config
from farajamh.pipeline import App, applicability

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    c = config(ROOT / "config.yaml")
    c["storage"] = str(tmp_path / "test.sqlite")
    for identity, profile in c["identities"].items():
        monkeypatch.setenv(profile["token_env"], "token-" + identity)
    return c


@pytest.fixture
def app(cfg):
    result = App(cfg)
    yield result
    result.store.db.close()


@pytest.fixture
def sources():
    return [json.loads(line) for line in (ROOT / "pilot/utterances.jsonl").read_text().splitlines()]


def review_payload(h, action="accept"):
    return {"action": action, "preferred": [copy.deepcopy(h)], "comment": "SIMULATED reviewer evidence comment", "evidence_refs": ["E1"],
        "uncertainties": [], "risk_signal": "not_flagged", "applicability_confirmed": False}


def reviewed(app, source):
    d = app.run(source)
    h = d["comparison"]["groups"][0]["hypotheses"][0]["hypothesis"]
    for identity in ("demo_ke", "demo_tz"):
        d = app.review(source["utterance_id"], review_payload(h), "token-" + identity, d["version"])
    return d, h


def adjudicated(app, source, action="approve"):
    d, h = reviewed(app, source)
    payload = {"action": action, "meanings": [h] if action == "approve" else [], "rationale": "SIMULATED human rationale", "evidence_refs": ["E1"], "risk_signal": "not_flagged"}
    return app.adjudicate(source["utterance_id"], payload, "token-demo_arbitrator", d["version"]), h


def curated(app, source):
    d, h = adjudicated(app, source)
    payload = {"sense_id": "FARAJA:test", "meaning_id": h["id"], "source_label": source["original_text"], "english_gloss": h["meaning"],
        "definition": "A reviewed synthetic sense", "synonyms": [], "cultural_applicability": "Synthetic context only", "example_refs": [source["utterance_id"]],
        "evidence_refs": ["E1"], "owner": "Test curator", "reuse_approved": True, "applicability": applicability(source)}
    return app.curate(source["utterance_id"], payload, "token-demo_curator", d["version"]), h


def approved_mapping(app, source):
    d, h = curated(app, source)
    payload = {"resource": "MFOEM", "action": "approve", "sense_id": "FARAJA:test", "candidate_id": "FIXTURE:MFOEM-emotional-pain",
        "predicate": "skos:relatedMatch", "rationale": "SIMULATED fit evidence", "evidence_refs": ["E1"]}
    return app.mapping(source["utterance_id"], payload, "token-demo_curator", d["version"]), h, payload
