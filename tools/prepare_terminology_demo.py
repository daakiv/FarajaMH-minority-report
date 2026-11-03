"""Prepare an explicitly simulated three-resource lookup example, preserving existing cases."""
import copy
import json
import os
from pathlib import Path

from farajamh.common import config, require, write_json
from farajamh.pipeline import App


def main():
    root = Path(__file__).resolve().parents[1]
    cfg = config(root / "config.yaml")
    require(cfg["mode"] == "fixture", "This demonstration requires fixture mode")
    token = os.environ["FARAJA_DEMO_KE_TOKEN"]
    output = root / "work/terminology-demo"
    source = json.loads((root / "pilot/utterances.jsonl").read_text().splitlines()[0])
    source["utterance_id"] = "TERM-TEST-01"
    fixtures = json.loads((root / "pilot/model_responses.json").read_text())
    write_json(output / "model_responses.json", {source["utterance_id"]: fixtures["SYN01"]})
    cfg["fixtures"] = str(output / "model_responses.json")
    app = App(cfg)
    try:
        require(not any(d["source"]["utterance_id"] == source["utterance_id"] for d in app.store.all()),
                "TERM-TEST-01 already exists; inspect it rather than overwrite it")
        app.identity(token, "reviewer")
        d = app.run(source)
        h = copy.deepcopy(d["models"][0]["output"]["hypotheses"][0])
        h.update(id="demo-emotional-pain", meaning="emotional pain", category="emotional",
                 search_terms=["emotional pain"], rationale="SIMULATED lookup demonstration using the loss context; physical alternatives remain in the model record.")
        payload = {"decision": {"action": "approve", "meanings": [h],
            "rationale": "SIMULATED software test: select emotional pain to exercise all three fictional terminology lookups. This is not a validated interpretation.",
            "evidence_refs": ["E1"], "risk_signal": "uncertain"},
            "annotations": {h["id"]: {"family_code": "E", "dap_categories": []}},
            "safety_note": "SIMULATED test: the physical discomfort alternative remains uncertain and requires separate assessment.",
            "applicability_confirmed": True, "second_opinion_requested": False}
        d = app.complete_review(source["utterance_id"], payload, token, d["version"])
        checks = []
        for resource, result in d["terminology"].items():
            require(result["state"] == "HITS" and result["candidates"], resource + " did not return candidates")
            for candidate in result["candidates"]:
                verified = app.resolver.verify(resource, candidate["id"], candidate["iri"])
                require(verified["fixture"] and verified["active"], "Expected active fictional candidate")
                checks.append({"resource": resource, "state": result["state"], "id": candidate["id"],
                               "label": candidate["label"], "release": candidate["release"], "fixture": True})
        require(len(checks) == 3, "Expected all three resources")
        require(not d["mapping_reviews"] and not d["sense_links"], "Lookup must not automatically approve mappings")
        report = {"case": source["utterance_id"], "version": d["version"], "query": "emotional pain",
                  "scope": "Scripted fictional lookup demonstration, not real ontology retrieval", "results": checks,
                  "local_concept_and_mapping_signoff": "Pending user testing"}
        write_json(output / "lookup-results.json", report)
        print(json.dumps(report, indent=2))
    finally:
        app.store.db.close()


if __name__ == "__main__":
    main()
