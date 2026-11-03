import copy

import pytest
from jsonschema import ValidationError

from farajamh.pipeline import applicability


def decision(d, action="approve"):
    h = copy.deepcopy(d["models"][0]["output"]["hypotheses"][0])
    h["id"] = "reviewed-1"
    h["category"] = "emotional"
    return {"decision": {"action": action, "meanings": [h] if action == "approve" else [],
            "rationale": "Synthetic context supports emotional pain", "evidence_refs": ["E1"], "risk_signal": "uncertain"},
        "annotations": {h["id"]: {"family_code": "E", "dap_categories": ["Depression"]}} if action == "approve" else {},
        "safety_note": "Uncertain safety needs separate assessment", "applicability_confirmed": True,
        "second_opinion_requested": False}


def test_one_reviewer_meaning_curation_mapping_and_correction(app, sources):
    d = app.run(sources[0])
    payload = decision(d)
    d = app.complete_review("SYN01", payload, "token-demo_ke", d["version"])
    assert d["state"] == "ADJUDICATED" and len(d["reviews"]) == 1
    assert d["adjudication"]["identity"]["id"] == "demo_ke"
    assert d["adjudication"]["workflow"] == "single_reviewer"
    assert d["priority"]["queue"] == "PRIORITY"
    concept = {"sense_id": "FARAJA:single", "meaning_id": "reviewed-1", "source_label": sources[0]["original_text"],
        "english_gloss": "Emotional pain", "definition": "Synthetic reviewed emotional pain", "synonyms": [],
        "cultural_applicability": "Synthetic context only", "example_refs": ["SYN01"], "evidence_refs": ["E1"],
        "owner": "demo_ke", "reuse_approved": False, "applicability": applicability(sources[0])}
    d = app.curate("SYN01", concept, "token-demo_ke", d["version"])
    assert app.store.senses()[0]["review_annotations"]["dap_categories"] == ["Depression"]
    assert app.triage(sources[0])["route"] == "NEW"
    mapping = {"resource": "MFOEM", "action": "approve", "sense_id": "FARAJA:single",
        "candidate_id": "FIXTURE:MFOEM-emotional-pain", "predicate": "skos:relatedMatch",
        "rationale": "Synthetic candidate is related, not identical", "evidence_refs": ["E1"]}
    d = app.mapping("SYN01", mapping, "token-demo_ke", d["version"])
    assert d["mapping_reviews"][0]["identity"]["id"] == "demo_ke"
    concept["reuse_approved"] = True
    d = app.curate("SYN01", concept, "token-demo_ke", d["version"])
    assert app.store.senses()[0]["version"] == 2
    assert app.triage(sources[0])["route"] == "KNOWN"
    d = app.complete_review("SYN01", decision(d, "request_context"), "token-demo_ke", d["version"])
    assert d["state"] == "NEEDS_CONTEXT" and not d["terminology"] and not d["mapping_reviews"]
    assert d["stale_artifacts"] and not app.sense_current(app.store.senses()[0])


def test_guided_lookup_uses_only_approved_terms(app, sources, monkeypatch):
    d = app.run(sources[0])
    calls = []
    monkeypatch.setattr(app.resolver, "search", lambda resource, queries: calls.append(queries) or {"resource":resource,"queries":queries,"candidates":[],"state":"NO_RESULTS"})
    p = decision(d, "unresolved")
    d = app.complete_review("SYN01", p, "token-demo_ke", d["version"])
    assert not calls
    p = decision(d)
    p["decision"]["meanings"][0]["search_terms"] = ["human edited meaning"]
    app.complete_review("SYN01", p, "token-demo_ke", d["version"])
    assert calls == [["human edited meaning"]] * 3


def test_second_opinion_requires_another_reviewer_even_after_new_evidence(app, sources):
    d = app.run(sources[0])
    p = decision(d, "unresolved")
    p["second_opinion_requested"] = True
    d = app.complete_review("SYN01", p, "token-demo_ke", d["version"])
    assert app.view("SYN01", "token-demo_tz")["adjudication"] is not None
    d = app.add_evidence("SYN01", {"id": "E2", "text": "Synthetic clarification", "reference": "dummy"}, "token-demo_ke", d["version"])
    with pytest.raises(ValueError, match="another reviewer"):
        app.complete_review("SYN01", decision(d), "token-demo_ke", d["version"])
    result = app.complete_review("SYN01", decision(d), "token-demo_tz", d["version"])
    assert result["state"] == "ADJUDICATED" and result["second_opinion_request"] is None


@pytest.mark.parametrize("change,error", [
    (lambda p: p.update(applicability_confirmed=False), "applicability"),
    (lambda p: p["decision"].update(evidence_refs=["invented"]), "Evidence"),
    (lambda p: p["annotations"].clear(), "annotations"),
    (lambda p: p["annotations"]["reviewed-1"].update(family_code="C"), "Category"),
    (lambda p: p["decision"].update(meanings=[]), "annotations"),
    (lambda p: p.update(safety_note=" "), None),
    (lambda p: p["annotations"]["reviewed-1"].update(dap_categories=["diagnosis"]), None),
])
def test_invalid_guided_submission_is_atomic(app, sources, change, error):
    d = app.run(sources[0])
    p = decision(d)
    change(p)
    with pytest.raises((ValueError, ValidationError), match=error):
        app.complete_review("SYN01", p, "token-demo_ke", d["version"])
    assert app.store.get("SYN01")["version"] == 1
    assert len(app.store.audit()) == 1


@pytest.mark.parametrize("risk,checks,ok", [
    ("not_flagged", ["self_harm_wording"], True),
    ("not_flagged", [], True),
    ("flagged", ["self_harm_wording"], False),
    ("uncertain", ["self_harm_wording"], False),
])
def test_blank_safety_note_only_for_no_concern(app, sources, risk, checks, ok):
    d = app.run(sources[0])
    p = decision(d)
    p["decision"]["risk_signal"] = risk
    p.update(safety_note="", safety_checks=checks)
    if ok:
        assert app.complete_review("SYN01", p, "token-demo_ke", d["version"])["adjudication"]["guided_review"]["safety_note"] == ""
    else:
        with pytest.raises(ValueError, match="safety assessment note"):
            app.complete_review("SYN01", p, "token-demo_ke", d["version"])


def test_stale_and_unauthorized_guided_submissions(app, sources):
    d = app.run(sources[0])
    p = decision(d)
    with pytest.raises(ValueError, match="Role"):
        app.complete_review("SYN01", p, "token-demo_curator", 1)
    app.complete_review("SYN01", p, "token-demo_ke", 1)
    with pytest.raises(ValueError, match="Stale"):
        app.complete_review("SYN01", p, "token-demo_ke", 1)
    assert app.store.get("SYN01")["version"] == 2


def test_multiple_meanings_and_category_codes(app, sources):
    d = app.run(sources[0])
    p = decision(d)
    other = copy.deepcopy(p["decision"]["meanings"][0])
    other.update(id="reviewed-2", category="cognitive", meaning="Persistent thinking")
    p["decision"]["meanings"].append(other)
    p["decision"]["action"] = "multiple"
    p["annotations"]["reviewed-2"] = {"family_code": "C", "dap_categories": []}
    result = app.complete_review("SYN01", p, "token-demo_ke", 1)
    assert len(result["adjudication"]["decision"]["meanings"]) == 2


def test_emotional_pain_returns_verified_fixtures_for_all_three_resources(app, sources):
    d = app.run(sources[0])
    assert not d["terminology"]
    payload = decision(d)
    payload["decision"]["meanings"][0]["search_terms"] = ["emotional pain"]
    result = app.complete_review("SYN01", payload, "token-demo_ke", d["version"])
    assert set(result["terminology"]) == {"MFOEM", "MFOMD", "SNOMED_CT"}
    for resource, lookup in result["terminology"].items():
        assert lookup["state"] == "HITS"
        assert lookup["queries"] == ["emotional pain"]
        assert len(lookup["candidates"]) == 1
        candidate = lookup["candidates"][0]
        assert candidate["id"] == f"FIXTURE:{resource}-emotional-pain"
        assert app.resolver.verify(resource, candidate["id"], candidate["iri"])["fixture"]
    assert not result["mapping_reviews"] and not result["sense_links"]
    assert app.store.get("SYN01")["terminology"] == result["terminology"]


def test_refresh_lookup_preserves_meaning_and_uses_saved_queries(app, sources):
    d = app.run(sources[2])
    with pytest.raises(ValueError, match='Approve meaning'):
        app.refresh_terminology('SYN03', {}, 'token-demo_ke', d['version'])
    p = decision(d)
    p['decision']['meanings'][0]['search_terms'] = ['social pressure']
    d = app.complete_review('SYN03', p, 'token-demo_ke', d['version'])
    original = copy.deepcopy(d['adjudication'])
    old_lookup = copy.deepcopy(d['terminology'])
    version = d['version']
    with pytest.raises(ValueError, match='Role not authorized'):
        app.refresh_terminology('SYN03', {}, 'token-demo_tz', version)
    d = app.refresh_terminology('SYN03', {}, 'token-demo_ke', version)
    assert d['version'] == version + 1 and d['adjudication'] == original
    assert d['terminology_history'][-1]['terminology'] == old_lookup
    assert not d['mapping_reviews']
    for resource, result in d['terminology'].items():
        assert result['state'] == 'HITS'
        assert result['queries'] == ['social pressure']
        assert result['candidates'][0]['id'] == f'FIXTURE:{resource}-social-pressure'
    with pytest.raises(ValueError, match='Stale version'):
        app.refresh_terminology('SYN03', {}, 'token-demo_ke', version)


def test_fixture_catalogue_search_and_identifier_validation(app):
    for resource in ['MFOEM', 'MFOMD', 'SNOMED_CT']:
        synonym = app.resolver.search(resource, ['interpersonal demands'])
        assert synonym['state'] == 'HITS'
        assert synonym['candidates'][0]['id'] == f'FIXTURE:{resource}-social-pressure'
        assert app.resolver.search(resource, ['paintbrush'])['state'] == 'NO_RESULTS'
        assert app.resolver.search(resource, ['xyzunknown'])['state'] == 'NO_RESULTS'
        with pytest.raises(ValueError, match='Nonexistent fixture'):
            app.resolver.verify(resource, 'FIXTURE:invented-id')


def test_refresh_invalidates_mapping_but_retains_local_concept(app, sources):
    from conftest import approved_mapping
    d, _, _ = approved_mapping(app, sources[0])
    senses = copy.deepcopy(d['sense_links'])
    meaning = copy.deepcopy(d['adjudication'])
    d = app.refresh_terminology('SYN01', {}, 'token-demo_ke', d['version'])
    assert all(m['stale'] for m in d['mapping_reviews'])
    assert d['sense_links'] == senses and d['adjudication'] == meaning
    assert app.sense_current(app.store.senses()[0])
