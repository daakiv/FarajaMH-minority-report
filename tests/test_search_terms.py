import json
import threading
import urllib.error
import urllib.request

import pytest

from conftest import ROOT
from farajamh.common import config
from farajamh.terminology import term_advice
from farajamh.webapp import server


def counts(**hits):
    return {r: {"count": n, "limit": 50, "examples": ["x"] * min(n, 3)} for r, n in hits.items()}


@pytest.mark.parametrize("term,hits,level,phrase", [
    ("cultural idiom", counts(MFOEM=0, MFOMD=0, SNOMED_CT=0), "remove", "Describes the expression"),
    ("somatic expression", counts(MFOEM=0, MFOMD=3, SNOMED_CT=4), "remove", "Describes the expression"),
    ("feeling muddled", counts(MFOEM=0, MFOMD=0, SNOMED_CT=0), "remove", "No hits in any source"),
    ("instability", counts(MFOEM=0, MFOMD=0, SNOMED_CT=119), "narrow", "Too broad in SNOMED CT (119 hits; only the first 50"),
    ("confusion", counts(MFOEM=2, MFOMD=5, SNOMED_CT=51), "narrow", "Finds concepts in MFOEM, MFOMD, but too broad in SNOMED CT"),
    ("disorientation", counts(MFOEM=0, MFOMD=4, SNOMED_CT=15), "ok", "Finds concepts in MFOMD, SNOMED CT."),
])
def test_term_advice(term, hits, level, phrase):
    result = term_advice(term, hits)
    assert result["level"] == level and phrase in result["advice"]


def test_unchecked_source_is_said_not_hidden():
    hits = {**counts(MFOEM=2, MFOMD=1), "SNOMED_CT": {"error": "TimeoutError"}}
    result = term_advice("worry", hits)
    assert result["level"] == "ok" and "Some sources could not be checked" in result["advice"]


def test_fixture_terms_are_counted(app):
    good, unknown = app.resolver.check_terms(["emotional pain", "xyzunknown"])
    assert good["level"] == "ok" and all(s["count"] >= 1 for s in good["sources"].values())
    assert unknown["level"] == "remove"


def test_term_check_endpoint(cfg):
    http = server(cfg, 0)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{http.server_port}/api/term_check"

    def post(body, token="token-demo_ke"):
        request = urllib.request.Request(base, json.dumps(body).encode(), {"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    try:
        status, body = post({"terms": ["emotional pain", " emotional pain ", "cultural idiom"]})
        assert status == 200 and [t["term"] for t in body["terms"]] == ["emotional pain", "cultural idiom"]
        assert body["terms"][1]["level"] == "remove"
        assert post({"terms": [f"t{i}" for i in range(11)]})[0] == 400
        assert post({"terms": ["worry"]}, token="wrong")[0] == 400
    finally:
        http.shutdown()
        http.server_close()


def test_live_config_uses_prompt_v3_with_search_term_rules():
    live = config(ROOT / "config.live-test.yaml")
    assert live["prompt"].endswith("interpret-v3.md")
    v2 = (ROOT / "farajamh/prompts/interpret-v2.md").read_text().split("\n", 1)[1]
    v3 = (ROOT / "farajamh/prompts/interpret-v3.md").read_text()
    # v3 keeps every v2 instruction and only adds the search-term rules.
    assert v2.strip() in v3 and "search_terms are typed into ontology search boxes" in v3
    assert "idiom, cultural, expression" in v3
