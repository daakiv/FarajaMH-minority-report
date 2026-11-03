import csv
from collections import Counter
from pathlib import Path

from .agreement import fleiss_kappa, primary
from .common import RESOURCES, write_json


PILOT_FIELDS = ["utterance_id", "language", "case_status", "state", "comparison_state", "priority_queue",
    "usable_readings", "failed_models", "model_seconds", "total_model_seconds", "dictionary_state", "dictionary_entries",
    "lookup_seconds", "lookup_states", "zero_hit_terms", "capped_terms", "decisions", "chosen_candidates",
    "literal_ratings", "contextual_ratings"]


def pilot_row(d: dict) -> dict:
    """One row per case for the pilot report. Ratings are reviewer judgements on synthetic test cases."""
    join = lambda items: "; ".join(str(x) for x in items)
    models = d["models"]
    lookups = d.get("terminology") or {}
    def coverage(resource):
        root = lookups.get(resource, {})
        parts = list(root.get("by_meaning", {}).values()) or [root]
        return [c for part in parts for c in part.get("search_coverage", [])]
    zero, capped = [], []
    for resource in RESOURCES:
        for c in coverage(resource):
            if c.get("returned") == 0:
                zero.append(resource + ":" + c["query"])
            elif c.get("total_reported") is None or c.get("returned", 0) < c["total_reported"]:
                capped.append(f"{resource}:{c['query']} ({c.get('returned')} of {c.get('total_reported')})")
    current = [m for m in d.get("mapping_reviews", []) if not m.get("stale")]
    def rank_of(m):
        meaning = next((s["meaning_id"] for s in d.get("sense_links", []) if s["id"] == m["decision"]["sense_id"]), None)
        root = lookups.get(m["decision"]["resource"], {})
        pool = (root.get("by_meaning", {}).get(meaning) or root).get("candidates", [])
        return next((c.get("rank") for c in pool if c["id"] == m["decision"].get("candidate_id")), None)
    ratings = ((d.get("adjudication") or {}).get("guided_review") or {}).get("model_ratings", {})
    dictionary = d.get("dictionary_evidence") or {}
    return {"utterance_id": d["source"]["utterance_id"], "language": d["source"].get("language"),
        "case_status": (d.get("case_flag") or {}).get("status", "active"), "state": d["state"],
        "comparison_state": d["comparison"]["state"], "priority_queue": d["priority"]["queue"],
        "usable_readings": sum(r.get("output") is not None for r in models),
        "failed_models": join(r["configuration_id"] for r in models if r["status"] == "FAILED"),
        "model_seconds": join(f"{r['configuration_id']}={round(r.get('runtime_seconds') or 0, 1)}" for r in models),
        "total_model_seconds": round(sum(r.get("runtime_seconds") or 0 for r in models), 1),
        "dictionary_state": dictionary.get("state"), "dictionary_entries": join(e["id"] for e in dictionary.get("entries", [])),
        "lookup_seconds": (d.get("terminology_lookup") or {}).get("seconds"),
        "lookup_states": join(f"{r}={lookups[r]['state']}" for r in RESOURCES if r in lookups),
        "zero_hit_terms": join(zero), "capped_terms": join(capped),
        "decisions": join(f"{m['decision']['resource']}={m['decision']['action']}" for m in current),
        "chosen_candidates": join(f"{m['decision']['resource']}={m['decision']['candidate_id']}@rank {rank_of(m)}" for m in current if m["decision"].get("candidate_id")),
        "literal_ratings": join(f"{k}={v['literal']}" for k, v in sorted(ratings.items())),
        "contextual_ratings": join(f"{k}={v['contextual']}" for k, v in sorted(ratings.items()))}


def rating_summary(dossiers: list[dict]) -> dict:
    """Counts per model, labelled with the number of rated cases; never presented as accuracy beyond this pack."""
    summary = {}
    for d in dossiers:
        ratings = ((d.get("adjudication") or {}).get("guided_review") or {}).get("model_ratings", {})
        for model, scores in ratings.items():
            row = summary.setdefault(model, {"rated_cases": 0, "literal": Counter(), "contextual": Counter()})
            row["rated_cases"] += 1
            row["literal"][scores["literal"]] += 1
            row["contextual"][scores["contextual"]] += 1
    return {m: {"rated_cases": v["rated_cases"], "literal": dict(v["literal"]), "contextual": dict(v["contextual"]),
        "scope": "Reviewer-rated, synthetic test pack only"} for m, v in summary.items()}


def report(app, directory: Path, include_flagged: bool = False) -> dict:
    everything = app.store.all()
    flagged = [d for d in everything if (d.get("case_flag") or {}).get("status") in ("test", "withdrawn")]
    dossiers = everything if include_flagged else [d for d in everything if d not in flagged]
    runs = [r for d in dossiers for r in d["models"]]
    states = Counter(d["comparison"]["state"] for d in dossiers)
    def rate(numerator, denominator):
        return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None}
    lookup = {}
    for resource in RESOURCES:
        searches = [d["terminology"][resource] for d in dossiers if resource in d["terminology"]]
        lookup[resource] = {"states": dict(Counter(s["state"] for s in searches)),
            "hit_rate": rate(sum(s["state"] == "HITS" for s in searches), len(searches)),
            "failure_rate": rate(sum(s["state"] in ("UNAVAILABLE", "SEARCH_FAILED") for s in searches), len(searches))}
    sim_reviews = [r for d in dossiers for r in d["reviews"] if r["identity"]["simulated"]]
    real_reviews = [r for d in dossiers for r in d["reviews"] if not r["identity"]["simulated"]]
    overrides = 0
    for d in dossiers:
        if d["adjudication"] and d["adjudication"]["identity"]["simulated"] and d["comparison"]["majority_group"]:
            group = next(g for g in d["comparison"]["groups"] if g["id"] == d["comparison"]["majority_group"])
            meanings = {h["hypothesis"]["meaning"] for h in group["hypotheses"]}
            if any(h["meaning"] not in meanings for h in d["adjudication"]["decision"]["meanings"]):
                overrides += 1
    majority_adjudicated = sum(bool(d["adjudication"] and d["adjudication"]["identity"]["simulated"] and d["comparison"]["majority_group"]) for d in dossiers)
    result = {"scope": "Software behavior only; fixture interpretations are not cultural evidence", "utterances": len(dossiers),
        "model_counts": {"selected": len(runs), "completed": sum(r["output"] is not None for r in runs),
            "failed": sum(r["status"] == "FAILED" for r in runs), "abstaining": sum(r["status"] == "ABSTAINED" for r in runs),
            "voting": sum(primary(r) is not None for r in runs)},
        "agreement_states": dict(states), "tie_rate": rate(states["TIED"], len(dossiers)),
        "no_majority_rate": rate(states["NO_MAJORITY"], len(dossiers)),
        "substantive_dissent_rate": rate(sum(d["comparison"]["substantive_dissent"] for d in dossiers), len(dossiers)),
        "dissent_retention": rate(sum(len(g["hypotheses"]) for d in dossiers for g in d["comparison"]["groups"] if g["standing"] in ("minority", "competing")),
                                sum(len(g["models"]) for d in dossiers for g in d["comparison"]["groups"] if g["standing"] in ("minority", "competing"))),
        "fleiss_kappa": fleiss_kappa(dossiers), "terminology": lookup,
        "simulated_review_metrics": {"submissions": len(sim_reviews), "minority_selection": rate(sum(r["decision"]["action"] == "minority" for r in sim_reviews), len(sim_reviews)),
            "adjudicator_override": rate(overrides, majority_adjudicated),
            "outcomes": dict(Counter(d["adjudication"]["decision"]["action"] for d in dossiers if d["adjudication"] and d["adjudication"]["identity"]["simulated"]))},
        "real_reviewer_metrics": "NOT MEASURED" if not real_reviews else {"submissions": len(real_reviews)},
        "unresolved": sum(d["state"] in ("UNRESOLVED", "NEEDS_CONTEXT") for d in dossiers),
        "gaps": sum(m["decision"]["action"] == "gap" and not m["stale"] for d in dossiers for m in d["mapping_reviews"]),
        "local_concepts": len(app.store.senses()),
        "review_completion": rate(sum(bool(d["adjudication"]) for d in dossiers), len(dossiers)),
        "runtime_per_model_utterance": [{"utterance_id": d["source"]["utterance_id"], "model": r["configuration_id"], "seconds": r["runtime_seconds"]} for d in dossiers for r in d["models"]],
        "runtime_per_utterance": {d["source"]["utterance_id"]: sum(r["runtime_seconds"] for r in d["models"]) for d in dossiers},
        "reviewer_ratings": rating_summary(dossiers),
        "excluded_cases": [] if include_flagged else [{"utterance_id": d["source"]["utterance_id"], "status": d["case_flag"]["status"]} for d in flagged]}
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "metrics.json", result)
    with (directory / "pilot-cases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=PILOT_FIELDS)
        writer.writeheader()
        writer.writerows(pilot_row(d) for d in dossiers)
    write_json(directory / "audit.json", app.store.audit())
    for d in dossiers:
        write_json(directory / "dossiers" / (d["source"]["utterance_id"] + ".json"), d)
    return result
