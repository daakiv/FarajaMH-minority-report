import copy
import json
import threading
import urllib.request

import pytest
import yaml

from conftest import ROOT, adjudicated, approved_mapping
from farajamh.agreement import compare
from farajamh.common import config, risk_terms_found
from farajamh.exports import export_readiness, export_sssom
from farajamh.webapp import server

LIVE_TERMS = yaml.safe_load((ROOT / "config.live-test.yaml").read_text())["risk"]["terms"]
V2 = "category-applicability-v2"


def test_live_config_uses_category_grouping():
    assert config(ROOT / "config.live-test.yaml")["voting"]["grouping_version"] == V2


def test_v2_groups_same_category_despite_free_text(app, sources):
    d = app.run(sources[3])
    frame = d["models"][0]["output"]["hypotheses"][0]["semantic_frame"]
    frame.update(cause="A differently worded cause", cultural_reading="Another model's cultural note")
    # v1 needs identical free-text frames, so the reworded reading splits off; v2 keeps it with the others.
    assert compare(d["models"], app.cfg["voting"])["state"] == "MAJORITY_WITH_DISSENT"
    assert compare(d["models"], {**app.cfg["voting"], "grouping_version": V2})["state"] == "UNANIMOUS"


@pytest.mark.parametrize("field,value", [("category", "somatic"), ("experiencer", "SYN-other"), ("assertion", "negated"), ("event_time", "past")])
def test_v2_still_splits_category_and_applicability(app, sources, field, value):
    d = app.run(sources[3])
    h = d["models"][0]["output"]["hypotheses"][0]
    if field == "category":
        h["category"] = value if h["category"] != value else "emotional"
    else:
        h["qualifiers"][field] = value
    c = compare(d["models"], {**app.cfg["voting"], "grouping_version": V2})
    assert c["state"] == "MAJORITY_WITH_DISSENT" and c["procedure"] == V2


@pytest.mark.parametrize("text,term", [
    ("Jarani anataka kijikata kitanzi", "kitanzi"),
    ("Nakia mimi sitaku kuwa kwa hii dunua tena", "hii dunia tena"),
    ("Anasema anataka kujinyoga", "kujinyonga"),
])
def test_risk_terms_match_exact_and_misspelled(text, term):
    assert term in risk_terms_found(text, LIVE_TERMS)


def test_short_risk_terms_need_exact_spelling():
    # "kujua" (to know) is one letter from "kujiua"; short terms are matched exactly only.
    assert risk_terms_found("Nataka kujua zaidi kuhusu kazi", LIVE_TERMS) == []


def test_misspelled_risk_term_sets_priority(app, sources):
    app.cfg["risk"]["terms"] = ["kujinyonga"]
    source = copy.deepcopy(sources[0])
    source["original_text"] = "Anasema anataka kujinyoga"
    assert app.priority(source, [])["queue"] == "PRIORITY"


def test_queue_surfaces_risk_terms_added_after_the_run(app, cfg, sources):
    d = app.run(sources[0])
    assert d["priority"]["queue"] == "STANDARD"
    cfg["risk"]["terms"] = cfg["risk"]["terms"] + [d["source"]["original_text"].split()[-1]]
    http = server(cfg, 0)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{http.server_port}/api/queue", headers={"Authorization": "Bearer token-demo_ke"})
        with urllib.request.urlopen(request) as response:
            item = json.load(response)["items"][0]
    finally:
        http.shutdown()
        http.server_close()
    assert item["priority"] == "PRIORITY" and app.store.get("SYN01")["priority"]["queue"] == "STANDARD"


def test_unsigned_case_is_not_ready_and_left_out(app, sources, tmp_path):
    approved_mapping(app, sources[0])
    d, _ = adjudicated(app, sources[1])
    uid = sources[1]["utterance_id"]
    blockers = export_readiness(app, d, app.identity("token-demo_curator"), True)["blockers"]
    assert any(b.startswith("Terminology sign-off incomplete: 0 of 3") for b in blockers)
    # The ready case still exports; the unfinished one is listed with its reason instead of stopping the package.
    result = export_sssom(app, tmp_path / "export", "token-demo_curator", True)
    assert result["rows"] == 1 and result["not_ready_cases"] == 1
    left_out = json.loads((tmp_path / "export/excluded-cases.json").read_text())
    assert [(c["utterance_id"], c["status"]) for c in left_out] == [(uid, "not_ready")]
    assert "Terminology sign-off incomplete" in left_out[0]["reason"]
    assert uid not in (tmp_path / "export/approved-synthetic.csv").read_text()


def test_changed_release_leaves_case_out(app, sources, tmp_path, monkeypatch):
    approved_mapping(app, sources[0])
    d, _ = adjudicated(app, sources[1])
    original = app.resolver.metadata
    monkeypatch.setattr(app.resolver, "metadata", lambda resource: original(resource) | {"release": "changed-release"})
    with pytest.raises(ValueError, match="left out: .*resource version changed"):
        export_sssom(app, tmp_path / "stale", "token-demo_curator", True)


def test_queue_and_view_carry_what_the_screen_shows(app, cfg, sources):
    d, _, _ = approved_mapping(app, sources[0])
    http = server(cfg, 0)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    base, headers = f"http://127.0.0.1:{http.server_port}", {"Authorization": "Bearer token-demo_curator"}
    try:
        with urllib.request.urlopen(urllib.request.Request(base + "/api/queue", headers=headers)) as response:
            queue = json.load(response)
        with urllib.request.urlopen(urllib.request.Request(base + "/api/dossier/SYN01", headers=headers)) as response:
            view = json.load(response)
    finally:
        http.shutdown()
        http.server_close()
    item = queue["items"][0]
    assert item["text"] == (d["source"].get("expression_span") or {}).get("text", d["source"]["original_text"])[:70]
    assert queue["search_limits"] == {r: s.get("limit", 10) for r, s in cfg["terminology"].items()}
    assert queue["include_lookup_only"] == bool(cfg["exports"].get("include_lookup_only"))
    # The concept form is filled from the saved concept, not from the meaning text.
    assert view["linked_senses"]["FARAJA:test"]["definition"] == "A reviewed synthetic sense"
    assert view["linked_senses"]["FARAJA:test"]["cultural_applicability"] == "Synthetic context only"
