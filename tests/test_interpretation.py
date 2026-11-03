import copy
import json
import socket

import pytest
from jsonschema import ValidationError

from farajamh.agreement import compare, fleiss_kappa
from farajamh.common import config, validate
from farajamh.models import call, interpret, validate_output
from farajamh.network import request
from farajamh.pilot import deny_network


@pytest.mark.parametrize("index,expected", [(0, "TIED"), (1, "MAJORITY_WITH_DISSENT"), (2, "NO_MAJORITY"), (3, "UNANIMOUS"), (16, "INSUFFICIENT_PARTICIPATION")])
def test_vote_cases(app, sources, index, expected):
    d = app.run(sources[index])
    assert d["comparison"]["state"] == expected
    assert d["state"] == "AWAITING_REVIEW"
    assert sum(len(g["hypotheses"]) for g in d["comparison"]["groups"]) == d["comparison"]["counts"]["voting"]
    if expected == "TIED":
        assert d["comparison"]["majority_group"] is None
        assert all(g["standing"] == "competing" for g in d["comparison"]["groups"])


def test_json_retry_and_persistent_failure(app, sources):
    d = app.run(sources[15])
    run = d["models"][0]
    assert len(run["attempts"]) == 2 and run["status"] == "COMPLETED"
    assert "validation_error" in run["attempts"][0]
    d = app.run(sources[16])
    assert d["models"][0]["status"] == "FAILED" and len(d["models"][0]["attempts"]) == 2


def test_abstention_and_participation(app, sources):
    d = app.run(sources[17])
    assert d["comparison"]["counts"] == {"selected": 4, "completed": 4, "failed": 0, "abstaining": 1, "voting": 3}
    assert d["comparison"]["state"] == "UNANIMOUS"
    assert len(d["models"][3]["output"]["hypotheses"]) == 1  # abstaining hypotheses preserved


def test_one_model_risk_priority(app, sources):
    app.cfg["risk"]["terms"] = []  # Isolate the model flag from the independent source lexicon.
    d = app.run(sources[6])
    assert d["priority"]["queue"] == "PRIORITY"
    assert d["comparison"]["counts"]["voting"] == 4


def test_uncertain_risk_priority(app, sources):
    assert app.run(sources[7])["priority"]["queue"] == "PRIORITY"


def test_secondary_hypotheses_never_extra_votes(app, sources):
    d = app.run(sources[1])
    for run in d["models"]:
        secondary = copy.deepcopy(run["output"]["hypotheses"][0])
        secondary["id"] = "secondary"
        run["output"]["hypotheses"].append(secondary)
    assert compare(d["models"], app.cfg["voting"])["counts"]["voting"] == 4


@pytest.mark.parametrize("field,value", [("experiencer", "SYN-other"), ("assertion", "negated"), ("event_time", "past")])
def test_contradictory_qualifiers_never_merge(app, sources, field, value):
    d = app.run(sources[3])
    d["models"][0]["output"]["hypotheses"][0]["qualifiers"][field] = value
    c = compare(d["models"], app.cfg["voting"])
    assert c["state"] == "MAJORITY_WITH_DISSENT" and c["substantive_dissent"]


def test_wording_difference_not_semantic_conflict(app, sources):
    d = app.run(sources[3])
    d["models"][0]["output"]["contextual_rendering"] = "Quite differently phrased translation"
    d["models"][0]["output"]["hypotheses"][0]["meaning"] = "A paraphrase with the same full semantic frame"
    assert compare(d["models"], app.cfg["voting"])["state"] == "UNANIMOUS"


def test_duplicate_configuration_cannot_vote(app, sources):
    d = app.run(sources[3])
    d["models"][1]["configuration_id"] = d["models"][0]["configuration_id"]
    with pytest.raises(ValueError): compare(d["models"], app.cfg["voting"])


def test_fleiss_undefined_single_category(app, sources):
    result = fleiss_kappa([app.run(sources[3])])
    assert result["value"] is None and result["expected_agreement"] == 1


def test_synthetic_and_identifiers(app, sources):
    source = copy.deepcopy(sources[0])
    source["synthetic"] = False
    with pytest.raises(ValidationError): app.run(source)
    source["synthetic"] = True
    source["original_text"] = "Contact me at person@example.org"
    with pytest.raises(ValueError, match="identifier"): app.run(source)


def test_model_cannot_inject_approval_or_evidence(app, sources):
    d = app.run(sources[0])
    output = copy.deepcopy(d["models"][0]["output"])
    output["approved"] = True
    with pytest.raises(ValidationError): validate_output(output, sources[0])
    del output["approved"]
    output["risk"]["evidence_refs"] = ["invented"]
    with pytest.raises(ValueError): validate_output(output, sources[0])


def test_independent_same_input_and_prompt(app, sources):
    d = app.run(sources[0])
    assert len({r["provenance"]["input_hash"] for r in d["models"]}) == 1
    assert len({r["provenance"]["prompt_hash"] for r in d["models"]}) == 1
    assert len({r["provenance"]["cache_key"] for r in d["models"]}) == 4


def test_network_blocked(cfg):
    with pytest.raises(ValueError, match="OFFLINE"): request(cfg, "http://127.0.0.1:11434/api/tags")
    with deny_network(), pytest.raises(RuntimeError, match="OFFLINE"):
        socket.create_connection(("example.org", 443))


def test_real_missing_model_is_failure(cfg, sources, monkeypatch):
    cfg["mode"] = "local"
    for m in cfg["models"]: m["provider"] = "ollama"
    monkeypatch.setattr("farajamh.models.network.request", lambda *a, **k: {"models": []})
    results = interpret(cfg, sources[0])
    assert len(results) == 4 and all(r["status"] == "FAILED" for r in results)


def test_ollama_success_records_actual_digest(cfg, sources, monkeypatch):
    cfg["mode"] = "local"
    model = cfg["models"][0] | {"provider": "ollama"}
    calls = []
    def request(cfg, url, payload=None):
        calls.append((url, payload))
        if url.endswith("/api/tags"):
            return {"models": [{"name": model["model"], "digest": "test-digest"}]}
        return {"model": model["model"], "message": {"content": '{"response":"test"}'}}
    monkeypatch.setattr("farajamh.models.network.request", request)
    messages = [{"role": "system", "content": "Test only"}]
    raw, meta = call(cfg, model, messages, sources[0], 0)
    assert meta["digest"] == "test-digest"
    assert calls[-1][1]["messages"] == messages and calls[-1][1]["keep_alive"] == 0


def test_openai_compatible_explicit_connected_and_env_key(cfg, sources, monkeypatch):
    cfg["mode"] = "connected"
    model = cfg["models"][0] | {"provider": "openai_compatible", "endpoint": "https://api.example.org/v1", "key_env": "FARAJA_API_KEY"}
    monkeypatch.setenv("FARAJA_API_KEY", "test-secret-not-in-provenance")
    def request(cfg, url, payload, token):
        assert url == "https://api.example.org/v1/chat/completions" and token == "test-secret-not-in-provenance"
        return {"model": "provider-reported-model", "system_fingerprint": "test-version", "choices": [{"message": {"content": "{}"}}]}
    monkeypatch.setattr("farajamh.models.network.request", request)
    raw, meta = call(cfg, model, [], sources[0], 0)
    assert meta["actual_model"] == "provider-reported-model" and "secret" not in json.dumps(meta)
    cfg["mode"] = "local"
    with pytest.raises(ValueError): call(cfg, model, [], sources[0], 0)


def test_dictionary_evidence_is_retrieved_after_blind_model_calls(app, sources, monkeypatch):
    from farajamh import models

    actual_call = models.call
    calls = []
    events = []
    marker = 'DICTIONARY-ONLY-MEANING-MUST-NOT-REACH-MODELS'

    def capture(cfg, model, messages, source, attempt):
        events.append('model')
        calls.append(copy.deepcopy(messages))
        return actual_call(cfg, model, messages, source, attempt)

    def lookup(source):
        events.append('dictionary')
        return {'route': 'KNOWN', 'references': [{'id': marker, 'version': 1}],
                'candidate': {'id': marker}, 'human_applicability_required': True}

    monkeypatch.setattr(models, 'call', capture)
    monkeypatch.setattr(app, 'triage', lookup)
    dossier = app.run(sources[15])  # Includes a schema retry, which must also stay blind.
    assert calls and events[-1] == 'dictionary'
    assert all(event == 'model' for event in events[:-1])
    assert marker not in json.dumps(calls)
    assert all('ckb_references_not_approvals' not in json.loads(messages[1]['content']) for messages in calls)
    assert len(dossier['models']) == len(app.cfg['models'])
    assert all(run['provenance']['reference_versions'] == [] for run in dossier['models'])
    assert dossier['triage']['references'][0]['id'] == marker
