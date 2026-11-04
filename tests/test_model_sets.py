"""Model sets (e.g. small local and large hosted): one set reads each case and the case records which."""
import copy
from pathlib import Path

import pytest
import yaml

from test_guided_review import decision
from farajamh.common import config
from farajamh.intake import IntakeError
from farajamh.jobs import Runs, model_availability
from farajamh.pipeline import App
from farajamh.reporting import scorecard

ROOT = Path(__file__).resolve().parents[1]
HOSTED = {"provider": "openai_compatible", "endpoint": "https://api.provider.example/v1", "key_env": "FARAJA_LLM_API_KEY",
    "settings": {"temperature": 0}}


def write_config(tmp_path, change):
    raw = yaml.safe_load((ROOT / "config.yaml").read_text())
    change(raw)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    return config(path)


def two_sets(raw):
    models = raw.pop("models")
    raw["model_profiles"] = {"small": {"label": "Small", "models": models}, "alt": {"label": "Alternative", "models": models[::-1]}}
    raw["model_profile"] = "small"


def test_a_plain_model_list_is_one_default_set():
    cfg = config(ROOT / "config.yaml")
    assert list(cfg["model_profiles"]) == ["default"] and cfg["model_profile"] == "default"
    assert cfg["models"] == cfg["model_profiles"]["default"]["models"] and cfg["model_profiles"]["default"]["hosted"] is False
    live = config(ROOT / "config.live-test.yaml")
    assert live["model_profile"] == "small" and [m["id"] for m in live["models"]] == ["gemma3:12b", "qwen2.5:7b", "llama3.1:8b"]


@pytest.mark.parametrize("change, message", [
    (lambda raw: raw.update(model_profiles={"x": {"models": raw["models"]}}), "either models or model_profiles"),
    (lambda raw: raw.update(model_profiles={"x": {"models": raw.pop("models")[:2]}}), "at least three"),
    (lambda raw: raw.update(model_profiles={"x": {"models": raw.pop("models")}}, model_profile="y"), "model_profile must name"),
    (lambda raw: raw.update(model_profiles={"Large Set": {"models": raw.pop("models")}}), "lowercase")])
def test_model_sets_are_checked(tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        write_config(tmp_path, change)


def test_hosted_sets_are_detected(tmp_path):
    def change(raw):
        raw["model_profiles"] = {"large": {"models": [dict(HOSTED, id=f"m{i}", model=f"model-{i}") for i in range(3)]},
            "cloud": {"models": [{"id": f"c{i}", "provider": "ollama", "model": f"gemma{i}:31b-cloud", "endpoint": "http://127.0.0.1:11434", "settings": {}} for i in range(3)]},
            "local": {"models": raw.pop("models")}}
    cfg = write_config(tmp_path, change)
    assert [cfg["model_profiles"][n]["hosted"] for n in ("large", "cloud", "local")] == [True, True, False]


def test_each_case_records_the_set_that_read_it(tmp_path, sources, cfg):  # cfg sets the demo tokens
    cfg = write_config(tmp_path, two_sets)
    cfg["_base"] = str(ROOT)  # resolve prompts and fixtures from the repository
    cfg["storage"] = str(tmp_path / "sets.sqlite")
    app = App(cfg)
    try:
        small = app.run(sources[0])
        alt = app.run(sources[1], profile="alt")
        assert small["model_set"]["name"] == "small" and alt["model_set"] == {"name": "alt", "label": "Alternative", "hosted": False,
            "models": [m["id"] for m in cfg["model_profiles"]["alt"]["models"]]}
        assert [r["configuration_id"] for r in alt["models"]] == alt["model_set"]["models"]
        with pytest.raises(ValueError, match="Unknown model set"):
            app.run(sources[2], profile="large")
        for d in (small, alt):
            app.complete_review(d["source"]["utterance_id"], decision(d), "token-demo_ke", d["version"])
        card = scorecard(app.store.all(), cfg["model_profiles"])
        assert {m["model_set"] for m in card["models"]} == {"small", "alt"}
        assert len(card["models"]) == 2 * len(cfg["models"]) and all(m["approved_cases"] == 1 for m in card["models"])
    finally:
        app.store.db.close()


def test_older_cases_are_matched_to_a_set_by_their_models(app, sources):
    d = app.run(sources[0])
    app.complete_review("SYN01", decision(d), "token-demo_ke", d["version"])
    older = app.store.all()
    for case in older:
        case.pop("model_set")  # as recorded before model sets existed
    assert {m["model_set"] for m in scorecard(older, app.cfg["model_profiles"])["models"]} == {"default"}
    assert {m["model_set"] for m in scorecard(older)["models"]} == {"not recorded"}


def test_hosted_availability_shows_whether_the_key_is_set_never_the_key(cfg, monkeypatch):
    cfg["model_profiles"]["large"] = {"label": "Large", "hosted": True, "models": [dict(HOSTED, id="m1", model="model-1")]}
    monkeypatch.delenv("FARAJA_LLM_API_KEY", raising=False)
    row = next(r for r in model_availability(cfg) if r["profile"] == "large")
    assert row["state"] == "hosted · key missing (set FARAJA_LLM_API_KEY)"
    monkeypatch.setenv("FARAJA_LLM_API_KEY", "secret-value")
    rows = model_availability(cfg)
    assert next(r for r in rows if r["profile"] == "large")["state"] == "hosted · key set" and "secret-value" not in str(rows)


def test_intake_refuses_an_unknown_model_set(cfg):
    cfg["mode"] = "connected"
    app, jobs = App(cfg), Runs(cfg)
    try:
        with pytest.raises(IntakeError) as error:
            jobs.start(app, {"model_profile": "large"}, {"id": "tester", "roles": ["reviewer"]})
        assert error.value.field == "model_profile"
    finally:
        jobs.pool.shutdown()
        app.store.db.close()
