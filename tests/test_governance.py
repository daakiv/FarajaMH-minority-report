import copy
import json
import sqlite3

import pytest

from farajamh.exports import export_sssom
from conftest import adjudicated, approved_mapping, curated, reviewed, review_payload


def test_independent_reviews_hidden(app, sources):
    app.cfg["review"]["workflow"] = "legacy"
    d = app.run(sources[0])
    h = d["comparison"]["groups"][0]["hypotheses"][0]["hypothesis"]
    app.review("SYN01", review_payload(h), "token-demo_ke", d["version"])
    assert app.view("SYN01", "token-demo_tz")["reviews"] == []
    assert len(app.view("SYN01", "token-demo_ke")["reviews"]) == 1


def test_roles_enforced(app, sources):
    d, h = reviewed(app, sources[0])
    payload = {"action": "approve", "meanings": [h], "rationale": "Test", "evidence_refs": ["E1"], "risk_signal": "not_flagged"}
    with pytest.raises(ValueError, match="Role"): app.adjudicate("SYN01", payload, "token-demo_ke", d["version"])
    with pytest.raises(ValueError): app.review("SYN01", review_payload(h), "token-demo_arbitrator", d["version"])
    with pytest.raises(ValueError): app.identity("untrusted", "reviewer")


def test_no_arbitration_without_review(app, sources):
    d = app.run(sources[0])
    h = d["comparison"]["groups"][0]["hypotheses"][0]["hypothesis"]
    payload = {"action": "approve", "meanings": [h], "rationale": "Test", "evidence_refs": ["E1"], "risk_signal": "not_flagged"}
    with pytest.raises(ValueError, match="HITL"): app.adjudicate("SYN01", payload, "token-demo_arbitrator", d["version"])


def test_minority_selection_persists(app, sources):
    d = app.run(sources[1])
    minority = d["comparison"]["groups"][-1]["hypotheses"][0]["hypothesis"]
    d = app.review("SYN02", review_payload(minority, "minority"), "token-demo_ke", d["version"])
    assert app.store.get("SYN02")["reviews"][0]["decision"]["preferred"][0] == minority
    assert d["adjudication"] is None


def test_stale_review_rollback(app, sources):
    d, h = reviewed(app, sources[0])
    before = len(app.store.audit())
    with pytest.raises(ValueError, match="Stale version"):
        app.review("SYN01", review_payload(h), "token-demo_ke", 1)
    assert app.store.get("SYN01")["version"] == d["version"]
    assert len(app.store.audit()) == before


def test_unresolved_blocks_release(app, sources, tmp_path):
    d, h = adjudicated(app, sources[0], "unresolved")
    assert d["terminology"] == {}
    with pytest.raises(ValueError, match="No adjudicated"):
        export_sssom(app, tmp_path / "no-release", "token-demo_curator", True)


def test_simulated_blocks_real_release(app, sources, tmp_path):
    approved_mapping(app, sources[0])
    with pytest.raises(ValueError, match="simulated"):
        export_sssom(app, tmp_path / "not-real", "token-demo_curator", False)


def test_new_review_invalidates_mapping_and_ckb(app, sources):
    d, h, _ = approved_mapping(app, sources[0])
    d = app.review("SYN01", review_payload(h), "token-demo_ke", d["version"])
    assert d["adjudication"] is None and d["mapping_reviews"] == [] and d["stale_artifacts"]
    assert not app.sense_current(app.store.senses()[0])


def test_correction_marks_previous_export_stale(app, sources, tmp_path):
    d, h, _ = approved_mapping(app, sources[0])
    export_sssom(app, tmp_path / "snapshot", "token-demo_curator", True)
    app.review("SYN01", review_payload(h), "token-demo_ke", d["version"])
    assert any(e["action"] == "EXPORT_STALE" for e in app.store.audit())


def test_ckb_context_mismatch_and_reuse(app, sources):
    curated(app, sources[0])
    source = copy.deepcopy(sources[0])
    source["utterance_id"] = "REUSE"
    source["speaker_ref"] = "SYN-new-person"
    source["qualifiers"]["experiencer"] = "SYN-new-person"
    source["qualifiers"]["utterance_time"] = "2026-05-01T12:00:00Z"
    d = app.run(source)
    assert d["triage"]["route"] == "KNOWN" and len(d["models"]) == len(app.cfg["models"]) and d["state"] == "AWAITING_REVIEW"
    sense = app.store.senses()[0]
    assert "qualifiers" not in sense["meaning"] and "utterance_time" not in sense["applicability"]
    source["conversation"] = "Different context entirely"
    assert app.triage(source)["route"] == "NEAR_MATCH"
    source["conversation"] = sources[0]["conversation"]
    source["qualifiers"]["assertion"] = "negated"
    assert app.triage(source)["route"] == "NEAR_MATCH"


def test_gap_separate_from_failure(app, sources):
    d, _ = curated(app, sources[3])
    payload = {"resource": "SNOMED_CT", "action": "gap", "sense_id": "FARAJA:test", "candidate_id": None, "predicate": None,
        "rationale": "No adequate concept in fictional release", "evidence_refs": ["E1"]}
    d = app.mapping("SYN04", payload, "token-demo_curator", d["version"])
    assert d["mapping_reviews"][0]["decision"]["action"] == "gap"
    with app.store.transaction():
        d["terminology"]["SNOMED_CT"]["state"] = "SEARCH_FAILED"
        app.store.save(d, d["version"])
    with pytest.raises(ValueError, match="not a semantic gap"):
        app.mapping("SYN04", payload, "token-demo_curator", d["version"])


def test_invented_and_inactive_targets_rejected(app, sources, monkeypatch):
    d, _ = curated(app, sources[0])
    payload = {"resource": "MFOEM", "action": "approve", "sense_id": "FARAJA:test", "candidate_id": "MFOEM:invented", "predicate": "skos:exactMatch", "rationale": "Test", "evidence_refs": ["E1"]}
    with pytest.raises(ValueError, match="not retrieved"): app.mapping("SYN01", payload, "token-demo_curator", d["version"])
    payload["candidate_id"] = "FIXTURE:MFOEM-emotional-pain"
    original = app.resolver.verify
    monkeypatch.setattr(app.resolver, "verify", lambda *args: original(*args) | {"active": False})
    with pytest.raises(ValueError, match="Inactive"): app.mapping("SYN01", payload, "token-demo_curator", d["version"])


def test_required_resource_missing_blocks_export(app, sources, tmp_path):
    d, _, _ = approved_mapping(app, sources[0])
    with app.store.transaction():
        d["terminology"]["SNOMED_CT"]["state"] = "UNAVAILABLE"
        app.store.save(d, d["version"])
    with pytest.raises(ValueError, match="SNOMED_CT"):
        export_sssom(app, tmp_path / "blocked", "token-demo_curator", True)


def test_changed_release_blocks_stale_export(app, sources, tmp_path, monkeypatch):
    approved_mapping(app, sources[0])
    original = app.resolver.metadata
    monkeypatch.setattr(app.resolver, "metadata", lambda resource: original(resource) | {"release": "changed-release"})
    with pytest.raises(ValueError, match="resource version changed"):
        export_sssom(app, tmp_path / "stale", "token-demo_curator", True)


def test_new_risk_reopens_known_ckb_candidate(app, sources):
    curated(app, sources[0])
    source = copy.deepcopy(sources[0])
    source["utterance_id"] = "RISK_REUSE"
    source["evidence"].append({"id": "E2", "text": "Synthetic new mention of kujidhuru", "reference": "synthetic:new-risk"})
    d = app.run(source)
    assert d["triage"]["route"] == "NEAR_MATCH" and d["priority"]["queue"] == "PRIORITY"
    assert len(d["models"]) == 4  # A missing fixture is an explicit failed attempt, not skipped interpretation.


def test_new_evidence_reopens(app, sources):
    d, _ = adjudicated(app, sources[0])
    d = app.add_evidence("SYN01", {"id": "E2", "text": "Contradictory synthetic context", "reference": "synthetic:test"}, "token-demo_ke", d["version"])
    assert d["state"] == "AWAITING_REVIEW" and d["adjudication"] is None


def test_append_only_source_and_audit(app, sources):
    d = app.run(sources[0])
    with pytest.raises(sqlite3.IntegrityError): app.store.db.execute("UPDATE sources SET body='{}'")
    with pytest.raises(sqlite3.IntegrityError): app.store.db.execute("DELETE FROM audit")
    with pytest.raises(ValueError, match="already exists"): app.run(sources[0])


def test_experimental_candidate_is_excluded_and_reported(app, sources, tmp_path, monkeypatch):
    from conftest import approved_mapping
    from farajamh.exports import export_sssom
    approved_mapping(app, sources[0])
    verify = app.resolver.verify
    def experimental(*args, **kwargs):
        return {**verify(*args, **kwargs), 'experimental_lookup_only': True}
    monkeypatch.setattr(app.resolver, 'verify', experimental)
    result = export_sssom(app, tmp_path/'excluded-export', 'token-demo_curator', demonstration=True)
    assert result['rows'] == 0 and result['excluded_mappings'] == 1
    import json
    excluded = json.loads((tmp_path/'excluded-export'/'excluded-mappings.json').read_text())
    assert excluded[0]['candidate_id'] == 'FIXTURE:MFOEM-emotional-pain'
    assert 'experimental' in excluded[0]['reason'].lower()


def test_stored_credential_hashed(app, monkeypatch):
    monkeypatch.delenv("FARAJA_DEMO_KE_TOKEN", raising=False)
    with pytest.raises(ValueError): app.identity("stored-token-for-ke-1234", "reviewer")
    app.store.set_credential("demo_ke", "stored-token-for-ke-1234")
    assert app.identity("stored-token-for-ke-1234", "reviewer")["id"] == "demo_ke"
    with pytest.raises(ValueError): app.identity("wrong-token-for-ke-12345", "reviewer")
    salt, digest = app.store.db.execute("SELECT salt,hash FROM credentials").fetchone()
    assert b"stored-token-for-ke-1234" not in salt + digest
    assert "stored-token" not in json.dumps(app.store.audit())
    with pytest.raises(ValueError, match="16"): app.store.set_credential("demo_ke", "short")
