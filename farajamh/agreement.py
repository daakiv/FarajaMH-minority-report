"""Conservative semantic-frame grouping v1; model frame equality is a proposal for review."""
from __future__ import annotations

import re
from collections import Counter

from .common import digest, require


def primary(run: dict) -> dict | None:
    output = run.get("output")
    if not output or output["primary_hypothesis"] is None:
        return None
    return next(h for h in output["hypotheses"] if h["id"] == output["primary_hypothesis"])


def normalize(value: str) -> str:
    # Negation and all words are retained; no stopword deletion or broad-category merging.
    return re.sub(r"\s+", " ", value.strip().casefold())


def compare(runs: list[dict], voting: dict) -> dict:
    require(len({r["configuration_id"] for r in runs}) == len(runs), "One vote per distinct configuration")
    groups = {}
    assignments = []
    aliases = voting.get("aliases", {})
    for run in runs:
        h = primary(run)
        if h is None:
            continue
        frame = {k: aliases.get(normalize(v), normalize(v)) for k, v in h["semantic_frame"].items()}
        # Equality of full contextual semantic frame; translations, broad categories or codes alone never group.
        negation_markers = sorted(set(re.findall(r"\b(?:no|not|without|denies|denied|never)\b", h["meaning"].casefold())))
        signature = {"frame": frame, "qualifiers": h["qualifiers"], "category": h["category"],
                     "meaning_negation_markers": negation_markers}
        # Unknown meaning frames are deliberately not treated as established equivalence.
        if frame["experience"] in ("unknown", "uncertain", "other"):
            signature["unresolved_model"] = run["configuration_id"]
        key = digest(signature)
        if key not in groups:
            groups[key] = {"id": "G" + str(len(groups) + 1), "signature": signature, "models": [], "hypotheses": []}
        group = groups[key]
        group["models"].append(run["configuration_id"])
        group["hypotheses"].append({"model": run["configuration_id"], "hypothesis": h})
        assignments.append({"model": run["configuration_id"], "group": group["id"], "signature": signature,
                            "evidence_refs": h["evidence_refs"], "reviewable": True})
    ordered = sorted(groups.values(), key=lambda g: -len(g["models"]))
    v = sum(len(g["models"]) for g in ordered)
    threshold = v // 2 + 1
    top = len(ordered[0]["models"]) if ordered else 0
    majority = None
    if v < voting["minimum_primary_votes"]:
        state = "INSUFFICIENT_PARTICIPATION"
    elif top >= threshold and top >= 2:
        state = "UNANIMOUS" if top == v else "MAJORITY_WITH_DISSENT"
        majority = ordered[0]["id"]
    elif sum(len(g["models"]) == top for g in ordered) > 1:
        state = "TIED"
    else:
        state = "NO_MAJORITY"
    risks = {r["output"]["risk"]["signal"] for r in runs if r.get("output")}
    substantive = len(ordered) > 1 or len(risks) > 1
    for g in ordered:
        g["standing"] = ("majority" if g["id"] == majority else "minority") if majority else "competing"
    return {"procedure": voting["grouping_version"], "assignments": assignments, "groups": ordered,
        "state": state, "strict_majority_threshold": threshold, "majority_group": majority,
        "counts": {"selected": len(runs), "completed": sum(r["output"] is not None for r in runs),
            "failed": sum(r["status"] == "FAILED" for r in runs), "abstaining": sum(r["status"] == "ABSTAINED" for r in runs), "voting": v},
        "substantive_dissent": substantive, "automatic_flags_reviewable": True,
        "escalation": substantive or state in ("TIED", "NO_MAJORITY", "INSUFFICIENT_PARTICIPATION") or bool(risks & {"flagged", "uncertain"}),
        "notice": "Agreement measures this grouping proposal, not truth or clinical certainty."}


def fleiss_kappa(dossiers: list[dict]) -> dict:
    eligible, excluded = [], 0
    panel = None
    for d in dossiers:
        runs = d["models"]
        ids = tuple(r["configuration_id"] for r in runs)
        if len(runs) != 4 or any(primary(r) is None for r in runs) or (panel is not None and ids != panel):
            excluded += 1
            continue
        panel = ids
        eligible.append(Counter(primary(r)["category"] for r in runs))
    if not eligible:
        return {"value": None, "eligible_items": 0, "excluded_items": excluded, "reason": "No fixed four-rater complete items"}
    n, k = len(eligible), 4
    pbar = sum((sum(v * v for v in c.values()) - k) / (k * (k - 1)) for c in eligible) / n
    totals = sum(eligible, Counter())
    pe = sum((v / (n * k)) ** 2 for v in totals.values())
    return {"value": (pbar - pe) / (1 - pe) if pe < 1 else None, "eligible_items": n, "excluded_items": excluded,
        "observed_pair_agreement": pbar, "expected_agreement": pe,
        "assumption": "Same four model configurations; primary distress category; complete items only; undefined when expected agreement=1"}
