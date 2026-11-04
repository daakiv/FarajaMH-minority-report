"""Step 5 review sampling of agreed cases, and the per-model scorecard against reviewer-approved meanings."""
import copy
import csv
from pathlib import Path

import pytest
import yaml

from test_guided_review import decision
from farajamh.common import config
from farajamh.pipeline import App, sample_draw
from farajamh.reporting import report, scorecard
from farajamh.workflow import progress

ROOT = Path(__file__).resolve().parents[1]


def sampled_app(cfg, rate):
    cfg["review"]["agreed_sample_rate"] = rate
    cfg["review"]["agreed_sample_seed"] = "test-seed"
    return App(cfg)


def test_every_case_is_reviewed_when_sampling_is_not_configured(app, sources):
    d = app.run(sources[3])  # SYN04: unanimous, standard queue
    assert d["routing"] == {"review_required": True, "reasons": ["sampling_not_configured"]}
    assert progress(d)["next_task"] == "meaning"


def test_agreed_cases_outside_the_sample_are_left_unreviewed(cfg, sources):
    app = sampled_app(cfg, 0)
    try:
        agreed = app.run(sources[3])
        assert agreed["routing"]["review_required"] is False
        assert agreed["routing"]["reasons"] == ["agreed_not_sampled"]
        assert agreed["routing"]["sample"]["draw"] == round(sample_draw("test-seed", "SYN04"), 6)
        assert progress(agreed)["next_task"] == "not_sampled"
        # Disagreement and safety signals are never sampled away.
        assert app.run(sources[0])["routing"] == {"review_required": True, "reasons": ["disagreement"]}
        assert "safety" in app.run(sources[7])["routing"]["reasons"]
        # A reviewer may still review a case that was not sampled; it then follows the normal workflow.
        reviewed = app.complete_review("SYN04", decision(agreed), "token-demo_ke", agreed["version"])
        assert reviewed["state"] == "ADJUDICATED" and progress(reviewed)["next_task"] == "terminology"
    finally:
        app.store.db.close()


def test_full_sample_and_unrecorded_applicability_require_review(cfg, sources):
    app = sampled_app(cfg, 1)
    try:
        assert app.run(sources[3])["routing"]["reasons"] == ["agreed_sampled"]
        source = copy.deepcopy(sources[4])
        source["qualifiers"]["event_time"] = "unknown"
        assert app.run(source)["routing"] == {"review_required": True, "reasons": ["applicability_unknown"]}
    finally:
        app.store.db.close()


def test_sample_draw_is_reproducible_and_spread():
    draws = [sample_draw("seed", f"CASE-{i}") for i in range(400)]
    assert draws == [sample_draw("seed", f"CASE-{i}") for i in range(400)]
    assert all(0 <= x < 1 for x in draws) and 20 < sum(x < 0.1 for x in draws) < 60
    assert sample_draw("other-seed", "CASE-1") != draws[1]


@pytest.mark.parametrize("review, message", [({"agreed_sample_rate": 1.5, "agreed_sample_seed": "s"}, "between 0 and 1"),
    ({"agreed_sample_rate": 0.1}, "agreed_sample_seed")])
def test_sampling_configuration_is_checked(tmp_path, review, message):
    raw = yaml.safe_load((ROOT / "config.yaml").read_text())
    raw["review"].update(review)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match=message):
        config(path)


def test_meaning_origin_must_be_a_reading_from_the_case(app, sources):
    d = app.run(sources[0])
    payload = decision(d)
    payload["meaning_origins"] = {"reviewed-1": {"model": d["models"][0]["configuration_id"], "hypothesis_id": "not-a-reading"}}
    with pytest.raises(ValueError, match="reading from this case"):
        app.complete_review("SYN01", copy.deepcopy(payload), "token-demo_ke", d["version"])
    payload["meaning_origins"] = {"other-meaning": {"model": d["models"][0]["configuration_id"], "hypothesis_id": d["models"][0]["output"]["hypotheses"][0]["id"]}}
    with pytest.raises(ValueError, match="not in this decision"):
        app.complete_review("SYN01", payload, "token-demo_ke", d["version"])


def test_scorecard_counts_each_model_against_the_approved_meaning(app, sources, tmp_path):
    d = app.run(sources[0])  # SYN01: tied, so every reading is competing rather than majority
    first = d["models"][0]
    payload = decision(d)
    payload["meaning_origins"] = {"reviewed-1": {"model": first["configuration_id"], "hypothesis_id": first["output"]["hypotheses"][0]["id"]}}
    usable = [r["configuration_id"] for r in d["models"] if r.get("output")]
    payload["model_ratings"] = {usable[0]: {"literal": "correct", "contextual": "correct"}, usable[1]: {"literal": "partly_correct", "contextual": "wrong"}}
    app.complete_review("SYN01", payload, "token-demo_ke", d["version"])
    app.run(sources[1])  # awaiting review: not counted
    card = scorecard(app.store.all())
    assert card["approved_cases"] == 1 and card["rated_cases"] == 1
    rows = {m["model"]: m for m in card["models"]}
    assert len(rows) == len(d["models"])
    top = rows[first["configuration_id"]]
    assert top["reading_used"] == top["reading_used_unchanged"] == top["minority_reading_used"] == 1
    assert top["interpretation_correct"] == 1 and rows[usable[1]]["interpretation_wrong"] == 1
    assert rows[usable[1]]["translation_partly_correct"] == 1 and rows[usable[1]]["reading_used"] == 0
    assert sum(m["usable_readings"] for m in rows.values()) == len(usable)
    result = report(app, tmp_path / "report")
    assert result["model_scorecard"] == card
    with (tmp_path / "report/model-scorecard.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == len(d["models"])
