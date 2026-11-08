"""Round 2 pilot additions: lookup cache, per-source rerun, safety checks, model ratings,
case status, pilot report and test-pack file intake."""
import copy
import csv
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from conftest import curated
from test_guided_review import decision
from test_review_improvements import batch
from farajamh import terminology
from farajamh.common import config
from farajamh.exports import export_readiness
from farajamh.intake import IntakeError, run_file
from farajamh.pipeline import App
from farajamh.reporting import report

ROOT = Path(__file__).resolve().parents[1]
IRI = "http://purl.obolibrary.org/obo/MFOEM_000028"


@pytest.fixture
def live(tmp_path, monkeypatch):
    cfg = config(ROOT / "config.live-test.yaml")
    cfg["storage"] = str(tmp_path / "live.sqlite")
    monkeypatch.setenv("FARAJA_DAVID_TOKEN", "token-david")
    return cfg


def fake_ols(calls):
    def request(cfg, url, *args, **kwargs):
        if "/search?" in url:
            calls.append("search")
            return {"response": {"docs": [{"iri": IRI}], "numFound": 1}}
        if "/parents?" in url:
            calls.append("parents")
            return {"_embedded": {"terms": [{"label": "negative emotion process"}]}}
        if "/hierarchicalAncestors" in url:
            calls.append("ancestors")
            return {"_embedded": {"terms": [{"label": "emotion process"}]}}
        if "/terms/" in url:
            calls.append("term")
            return {"iri": IRI, "label": "anxiety", "description": ["A negative emotion."], "is_obsolete": False}
        return {"config": {"version": cfg["terminology"]["MFOEM"]["release"]}}
    return request


def test_ols_search_is_cached_but_verification_before_approval_is_live(live, monkeypatch):
    calls = []
    monkeypatch.setattr("farajamh.network.request", fake_ols(calls))
    terminology.clear_cache()
    first = terminology.Resolver(live).search("MFOEM", ["anxiety"])
    second = terminology.Resolver(live).search("MFOEM", ["anxiety"])  # a new request, as a new screen action would make
    assert calls == ["search", "term", "ancestors", "parents"]
    assert first["candidates"][0]["parents"] == ["negative emotion process"]
    assert first["candidates"][0]["domain"] == "emotion"
    assert first["search_coverage"][0]["cache_used"] is False and second["search_coverage"][0]["cache_used"] is True
    assert second["candidates"][0]["id"] == "MFOEM:000028"
    second["candidates"][0]["label"] = "changed by caller"
    assert terminology.Resolver(live).search("MFOEM", ["anxiety"])["candidates"][0]["label"] == "anxiety"
    terminology.Resolver(live).verify("MFOEM", "MFOEM:000028", IRI)
    assert calls == ["search", "term", "ancestors", "parents", "term"]
    terminology.clear_cache()


def test_rerun_one_source_keeps_the_others_and_stales_only_its_decisions(app, sources):
    d, _ = curated(app, sources[0])
    d = app.signoff("SYN01", batch(d), "token-demo_curator", d["version"])
    before = copy.deepcopy(d["terminology"])
    d = app.refresh_terminology("SYN01", {"resources": ["SNOMED_CT"]}, "token-demo_curator", d["version"])
    current = {m["decision"]["resource"] for m in d["mapping_reviews"] if not m["stale"]}
    assert current == {"MFOEM", "MFOMD"}
    assert d["terminology"]["MFOEM"] == before["MFOEM"] and d["terminology"]["MFOMD"] == before["MFOMD"]
    assert d["terminology"]["SNOMED_CT"]["timestamp"] != before["SNOMED_CT"]["timestamp"]
    assert d["terminology_lookup"]["resources"] == ["SNOMED_CT"]
    assert app.store.audit()[-1]["body"]["decision"]["resources"] == ["SNOMED_CT"]
    for payload in ({"resources": ["LOINC"]}, {"resources": []}, {"terms": ["x"]}):
        with pytest.raises(ValueError):
            app.refresh_terminology("SYN01", payload, "token-demo_curator", d["version"])


def test_bare_none_is_not_a_safety_assessment_without_checks(app, sources):
    d = app.run(sources[0])
    payload = decision(d)
    payload["safety_note"] = "None."
    with pytest.raises(IntakeError) as error:
        app.complete_review("SYN01", payload, "token-demo_ke", d["version"])
    assert error.value.field == "safety_note" and app.store.get("SYN01")["version"] == d["version"]
    payload["safety_checks"] = ["self_harm_wording", "harm_to_others", "crisis_or_urgency"]
    d = app.complete_review("SYN01", payload, "token-demo_ke", d["version"])
    assert d["adjudication"]["guided_review"]["safety_checks"][0] == "self_harm_wording"
    payload["safety_checks"] = ["looked_carefully"]
    with pytest.raises(ValidationError):
        app.complete_review("SYN01", payload, "token-demo_ke", d["version"])


def test_model_ratings_are_kept_and_limited_to_usable_readings(app, sources):
    d = app.run(sources[0])
    usable = [r["configuration_id"] for r in d["models"] if r.get("output")]
    payload = decision(d)
    payload["model_ratings"] = {usable[0]: {"literal": "correct", "contextual": "cannot_assess"}}
    saved = app.complete_review("SYN01", copy.deepcopy(payload), "token-demo_ke", d["version"])
    assert saved["adjudication"]["guided_review"]["model_ratings"][usable[0]]["contextual"] == "cannot_assess"
    payload["model_ratings"] = {"not-a-model": {"literal": "wrong", "contextual": "wrong"}}
    with pytest.raises(IntakeError) as error:
        app.complete_review("SYN01", payload, "token-demo_ke", saved["version"])
    assert error.value.field == "model_ratings"
    payload["model_ratings"] = {usable[0]: {"literal": "good", "contextual": "wrong"}}
    with pytest.raises(ValidationError):
        app.complete_review("SYN01", payload, "token-demo_ke", saved["version"])


def test_case_status_keeps_the_record_but_leaves_it_out_of_counts_and_exports(app, sources, tmp_path):
    first = app.run(sources[0])
    app.run(sources[1])
    with pytest.raises(IntakeError):
        app.flag_case("SYN01", {"status": "deleted", "reason": "x"}, "token-demo_ke", first["version"])
    with pytest.raises(IntakeError):
        app.flag_case("SYN01", {"status": "test", "reason": " "}, "token-demo_ke", first["version"])
    d = app.flag_case("SYN01", {"status": "test", "reason": "Software walkthrough entry"}, "token-demo_ke", first["version"])
    assert d["case_flag"]["status"] == "test" and d["models"] == first["models"] and d["version"] == first["version"] + 1
    with pytest.raises(ValueError, match="already has this status"):
        app.flag_case("SYN01", {"status": "test", "reason": "again"}, "token-demo_ke", d["version"])
    assert export_readiness(app, d, app.identity("token-demo_curator"), demonstration=True)["status"] == "EXCLUDED"
    result = report(app, tmp_path / "report")
    assert result["utterances"] == 1 and result["excluded_cases"] == [{"utterance_id": "SYN01", "status": "test"}]
    rows = list(csv.DictReader((tmp_path / "report/pilot-cases.csv").open()))
    assert [r["utterance_id"] for r in rows] == ["SYN02"] and rows[0]["usable_readings"]
    everything = report(app, tmp_path / "all", include_flagged=True)
    assert everything["utterances"] == 2
    restored = app.flag_case("SYN01", {"status": "active", "reason": "Back in the pilot"}, "token-demo_ke", d["version"])
    assert restored["case_flag"]["previous"] == "test"


def test_pilot_row_reports_ratings_lookup_and_chosen_candidate_rank(app, sources, tmp_path):
    d = app.run(sources[0])
    payload = decision(d)
    model = next(r["configuration_id"] for r in d["models"] if r.get("output"))
    payload["model_ratings"] = {model: {"literal": "partly_correct", "contextual": "wrong"}}
    d = app.complete_review("SYN01", payload, "token-demo_ke", d["version"])
    assert d["terminology_lookup"]["seconds"] >= 0
    result = report(app, tmp_path / "report")
    row = next(csv.DictReader((tmp_path / "report/pilot-cases.csv").open()))
    assert row["literal_ratings"] == model + "=partly_correct" and row["contextual_ratings"] == model + "=wrong"
    assert "MFOEM=HITS" in row["lookup_states"] and row["lookup_seconds"]
    assert result["reviewer_ratings"][model]["rated_cases"] == 1
    assert result["reviewer_ratings"][model]["scope"] == "Reviewer-rated, synthetic test pack only"


def write_pack(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pack_row(uid, text, expression, **extra):
    return {"utterance_id": uid, "original_text": text, "expression_text": expression, "occurrence": "",
        "language": "sw", "experiencer": "self", "assertion": "affirmed", "event_time": "unknown",
        "setting": "synthetic test", "conversation_context": "", "synthetic": "yes", **extra}


def test_test_pack_file_is_checked_in_full_before_any_model_call(live, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("farajamh.pipeline.interpret", lambda cfg, source, progress=None: calls.append(source["utterance_id"]) or [])
    app = App(live)
    try:
        good = pack_row("PACK-01", "Kabla ya mkutano na bosi, nasikia moyo inadunda, roho inaenda mbio.", "moyo inadunda, roho inaenda mbio")
        bad = pack_row("PACK-02", "Siku hizi kichwa imejaa ngori, siwezi lala.", "kichwa kimejaa ngori")
        pack = tmp_path / "pack.csv"
        write_pack(pack, [good, bad])
        with pytest.raises(IntakeError, match="case 2 \\(PACK-02\\) expression_text"):
            run_file(app, pack, "token-david")
        write_pack(pack, [good, dict(good)])
        with pytest.raises(IntakeError, match="already exists"):
            run_file(app, pack, "token-david")
        assert calls == [] and not app.store.all()
        bad["expression_text"] = "kichwa imejaa ngori"
        bad["language"] = "sw-x-sheng"
        jsonl = tmp_path / "pack.jsonl"
        jsonl.write_text("\n".join(json.dumps(r) for r in (good, bad)) + "\n")
        result = run_file(app, jsonl, "token-david")
        assert result["count"] == 2 and calls == ["PACK-01", "PACK-02"]
        saved = app.store.get("PACK-02")["source"]
        assert saved["language"] == "sw-x-sheng" and saved["expression_span"] == {"start": 10, "end": 29, "text": "kichwa imejaa ngori"}
        assert [e["action"] for e in app.store.audit()].count("CASE_ENTERED") == 2
    finally:
        app.store.db.close()
