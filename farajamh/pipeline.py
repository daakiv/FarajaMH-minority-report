from __future__ import annotations

import hmac
import json
import os
from difflib import SequenceMatcher
from time import monotonic

from .dictionary import evidence as dictionary_evidence
from .agreement import compare
from .common import CATEGORY_FAMILIES, RESOURCES, canonical, code_hash, digest, evidence_check, now, require, resolve, scan_identifiers, validate
from .models import interpret
from .workflow import progress as case_progress, steps as workflow_steps
from .storage import Store
from .terminology import Resolver


SAFETY_CHECKS = ("self_harm_wording", "harm_to_others", "crisis_or_urgency")
EMPTY_NOTES = {"none", "nil", "no", "n/a", "na", "-", "nothing", "ok", "fine"}
CASE_STATUSES = ("active", "test", "withdrawn")


def field_error(field, message):
    from .intake import IntakeError
    return IntakeError(field, message)


def excluded_case(d: dict) -> bool:
    """Test and withdrawn cases stay in the record but are left out of pilot counts and exports."""
    return (d.get("case_flag") or {}).get("status") in ("test", "withdrawn")


SAMPLING_PROCEDURE = "sha256(seed|utterance_id)-v1"


def sample_draw(seed: str, uid: str) -> float:
    """Reproducible uniform draw in [0, 1): anyone with the seed can recheck which cases were sampled."""
    return int(digest(seed + "|" + uid)[:13], 16) / 16 ** 13


def applicability(source: dict) -> dict:
    q = source["qualifiers"]
    time = q["event_time"].casefold()
    scope = "recurrent" if time == "recurrent" else "past" if "past" in time else ("future" if "future" in time else ("present" if time == "present" else "unknown"))
    return {k: source[k] for k in ("language", "region_variety", "conversation")} | {
        "assertion": q["assertion"], "attribution": q["attribution"], "temporal_scope": scope, "setting": q["setting"]}


class App:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.store = Store(resolve(cfg, cfg["storage"]))
        self.resolver = Resolver(cfg)

    def identity(self, token: str, role: str | None = None) -> dict:
        require(token, "Authentication token required")
        found = []
        for identity, profile in self.cfg["identities"].items():
            secret = os.environ.get(profile["token_env"], "")
            if (secret and hmac.compare_digest(token, secret)) or self.store.check_credential(identity, token):
                found.append({"id": identity, **profile})
        require(len(found) == 1, "Invalid or ambiguous authentication token")
        person = found[0]
        require(role is None or role in person["roles"], "Role not authorized")
        require(not person["simulated"] or self.cfg["mode"] == "fixture", "Simulated accounts only in fixture mode")
        return {k: v for k, v in person.items() if k != "token_env"}

    def priority(self, source: dict, runs: list[dict]) -> dict:
        evidence = []
        for term in self.cfg["risk"]["terms"]:
            if term.casefold() in canonical(source).casefold():
                evidence.append({"origin": "source_lexicon", "term": term, "reviewable": True})
        for run in runs:
            if run["output"] and run["output"]["risk"]["signal"] in self.cfg["risk"]["priority_signals"]:
                evidence.append({"origin": run["configuration_id"], "risk": run["output"]["risk"]})
            # Even invalid outputs remain risk-screened, but are never votes.
            for attempt in run["attempts"]:
                for term in self.cfg["risk"]["terms"]:
                    if term.casefold() in attempt.get("raw", "").casefold():
                        evidence.append({"origin": run["configuration_id"], "term": term, "reviewable": True})
        return {"queue": "PRIORITY" if evidence else "STANDARD", "evidence": evidence,
                "notice": "Research review priority only; no patient contact, diagnosis or treatment"}

    def routing(self, d: dict) -> dict:
        """Step 5: disagreements, safety flags and unrecorded who/negation/time always go to review; agreed cases are sampled."""
        q = d["source"]["qualifiers"]
        reasons = (["safety"] if d["priority"]["queue"] == "PRIORITY" else []) + (["disagreement"] if d["comparison"]["escalation"] else []) + (
            ["applicability_unknown"] if any(q[k] in ("unknown", "uncertain") for k in ("experiencer", "assertion", "event_time")) else [])
        rate = self.cfg["review"].get("agreed_sample_rate")
        if reasons or rate is None:
            return {"review_required": True, "reasons": reasons or ["sampling_not_configured"]}
        seed = self.cfg["review"]["agreed_sample_seed"]
        draw = sample_draw(seed, d["source"]["utterance_id"])
        return {"review_required": draw < rate, "reasons": ["agreed_sampled" if draw < rate else "agreed_not_sampled"],
            "sample": {"rate": rate, "seed": seed, "draw": round(draw, 6), "procedure": SAMPLING_PROCEDURE}}

    def sense_current(self, sense: dict) -> bool:
        d = self.store.get(sense["origin_utterance"])
        return bool(d.get("adjudication") and d["adjudication"]["decision_hash"] == sense["meaning_decision_hash"]
                    and d["state"] == "ADJUDICATED")

    def triage(self, source: dict) -> dict:
        references, known = [], []
        for sense in self.store.senses():
            if not sense["reuse_approved"] or not self.sense_current(sense):
                continue
            similarity = SequenceMatcher(None, source["original_text"].casefold(), sense["source_label"].casefold()).ratio()
            if similarity < 0.65:
                continue
            references.append(sense)
            required = applicability(source)
            if similarity == 1 and sense["applicability"] == required:
                known.append(sense)
        return {"route": "KNOWN" if len(known) == 1 else ("NEAR_MATCH" if references else "NEW"),
                "references": references, "candidate": known[0] if len(known) == 1 else None,
                "human_applicability_required": True}

    def check_mode(self, dossier=None):
        modes = {row[0] for row in self.store.db.execute("SELECT DISTINCT json_extract(body, '$.mode') FROM revisions")}
        require(not modes or modes == {self.cfg["mode"]}, "Database environment differs from running configuration; changes refused")
        if dossier is not None:
            require(dossier.get("mode") == self.cfg["mode"], "Case mode differs from running configuration; changes refused")

    def run(self, source: dict, progress=None, actor=None, profile=None) -> dict:
        self.check_mode()
        profile = profile or self.cfg["model_profile"]
        require(profile in self.cfg["model_profiles"], "Unknown model set")
        # Each case is read by one model set only, so small- and large-model readings are never pooled.
        run_cfg = {**self.cfg, "models": self.cfg["model_profiles"][profile]["models"]}
        emit = progress or (lambda event: None)
        validate("source", source)
        scan_identifiers(source)
        span = source.get("expression_span")
        if span:
            require(span["start"] < span["end"] <= len(source["original_text"]) and source["original_text"][span["start"]:span["end"]] == span["text"], "Expression span must exactly match original text")
        require(len({e["id"] for e in source["evidence"]}) == len(source["evidence"]), "Duplicate evidence IDs")
        for span in source["language_spans"]:
            require(span["start"] < span["end"] <= len(source["original_text"]), "Invalid language span")
        require(not self.store.db.execute("SELECT 1 FROM sources WHERE id=?", (source["utterance_id"],)).fetchone(), "Utterance already exists; immutable input")
        # Infographic v9.1: first-pass interpretations precede dictionary exposure.
        emit({"stage": "input_checked", "models": len(run_cfg["models"]), "model_set": profile})
        runs = interpret(run_cfg, source, progress) if progress else interpret(run_cfg, source)
        triage = self.triage(source)
        dictionary = dictionary_evidence(self.cfg, source)
        emit({"stage": "dictionary", "state": dictionary.get("state", "CHECKED"), "count": len(dictionary.get("entries", []))})
        pre_risk = self.priority(source, [])
        # New risk and unknown qualifiers reopen, rather than bypass generation through a known entry.
        unknown = any(v in ("unknown", "uncertain") for v in source["qualifiers"].values())
        if triage["route"] == "KNOWN" and (pre_risk["queue"] == "PRIORITY" or unknown):
            triage["route"] = "NEAR_MATCH"
            triage["reason"] = "New/current-context risk or unresolved qualifier requires interpretation"
        d = {"schema_version": "1.0", "source": source, "version": 0, "created_at": now(),
            "mode": self.cfg["mode"], "model_set": {"name": profile, "label": self.cfg["model_profiles"][profile]["label"],
                "hosted": self.cfg["model_profiles"][profile]["hosted"], "models": [m["id"] for m in run_cfg["models"]]}, "state": "AWAITING_REVIEW", "triage": triage, "dictionary_evidence": dictionary,
            "normalization": {"text": source["original_text"], "changes": [], "uncertainty": "No automatic normalization; original preserved"},
            "models": runs, "comparison": compare(runs, self.cfg["voting"]), "priority": self.priority(source, runs),
            "reviews": [], "adjudication": None, "terminology": {}, "mapping_reviews": [], "sense_links": [],
            "external_evidence": [], "stale_artifacts": [],
            "provenance": {"config_hash": digest(self.cfg), "code_hash": code_hash(),
                "upstream_commit": "a7cb9cbf90cffb186c69699b5a188f970d22e5b9", "synthetic": True}}
        d["routing"] = self.routing(d)
        emit({"stage": "comparison", "state": d["comparison"]["state"], "usable": d["comparison"]["counts"]["voting"], "groups": len(d["comparison"]["groups"]), "queue": d["priority"]["queue"],
            "review_required": d["routing"]["review_required"]})
        with self.store.transaction():
            self.check_mode()
            self.store.save(d)
            self.store.event("application", "INTERPRETATION_RECORDED", source["utterance_id"], d)
            if actor:
                self.store.event(actor, "CASE_ENTERED", source["utterance_id"], {"synthetic": True, "expression_span": source.get("expression_span")})
        emit({"stage": "record_saved", "version": d["version"]})
        return d

    def run_expression(self, uid, payload, token, expected):
        person = self.identity(token, "reviewer")
        parent = self.store.get(uid)
        self.check_mode(parent)
        require(parent["version"] == expected, "Stale version: refresh the dossier")
        require(set(payload) == {"utterance_id", "start", "end", "text"}, "Supply expression ID and exact span")
        source = dict(parent["source"])
        source.update(utterance_id=payload["utterance_id"], parent_utterance_id=uid,
            expression_span={k:payload[k] for k in ("start", "end", "text")})
        d = self.run(source)
        with self.store.transaction():
            self.store.event(person["id"], "EXPRESSION_REVIEW_CREATED", d["source"]["utterance_id"],
                {"parent_utterance_id":uid,"parent_version":expected,"expression_span":source["expression_span"]})
        return d

    def check_refs(self, d: dict, refs: list[str]):
        evidence_check(refs, {"evidence": d["source"]["evidence"] + d["external_evidence"]})

    def invalidate(self, d: dict, reason: str):
        if d.get("adjudication") or d["mapping_reviews"] or d["sense_links"]:
            d["stale_artifacts"].append({"version": d["version"], "reason": reason,
                "adjudication": d["adjudication"], "mapping_reviews": d["mapping_reviews"], "sense_links": d["sense_links"], "terminology": d["terminology"]})
        state = "AWAITING_REVIEW" if self.cfg["review"].get("workflow") == "single_reviewer" else "AWAITING_ARBITRATION"
        d.update(adjudication=None, mapping_reviews=[], sense_links=[], terminology={}, state=state)

    def save_action(self, d, person, action, payload, expected):
        self.check_mode(d)
        self.store.save(d, expected)
        self.store.event(person["id"], action, d["source"]["utterance_id"],
            {"identity": person, "decision": payload, "reviewed_version": expected, "result_version": d["version"], "timestamp": now()})
        for event in self.store.audit():
            if event["action"] in ("RELEASE_EXPORT", "DEMONSTRATION_EXPORT") and d["source"]["utterance_id"] in event["body"].get("versions", {}):
                self.store.event("application", "EXPORT_STALE", event["entity"],
                    {"utterance_id": d["source"]["utterance_id"], "new_version": d["version"], "reason": action})

    def review(self, uid: str, payload: dict, token: str, expected: int) -> dict:
        person = self.identity(token, "reviewer")
        validate("review", payload)
        scan_identifiers(payload)
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            self.check_refs(d, payload["evidence_refs"])
            for h in payload["preferred"]:
                self.check_refs(d, h["evidence_refs"])
            require(payload["preferred"] or payload["action"] in ("request_context", "reject", "unresolved"), "Preferred meaning required")
            if payload["action"] == "confirm_ckb":
                require(d["triage"]["route"] == "KNOWN" and payload["applicability_confirmed"], "Explicit contextual applicability required")
            self.invalidate(d, "Reviewer submission or correction")
            submission = {"identity": person, "decision": payload, "timestamp": now(), "reviewed_version": expected}
            # Append independent submissions; latest per identity is active, older ones remain visible.
            d["reviews"].append(submission)
            if payload["risk_signal"] in self.cfg["risk"]["priority_signals"]:
                d["priority"]["queue"] = "PRIORITY"
                d["priority"]["evidence"].append(submission)
            latest = {r["identity"]["id"]: r for r in d["reviews"]}
            d["reviewer_disagreement"] = len({digest(r["decision"]["preferred"]) for r in latest.values()}) > 1
            d["state"] = "AWAITING_ARBITRATION" if len(latest) >= self.cfg["review"]["minimum_reviewers"] else "AWAITING_REVIEW"
            self.save_action(d, person, "HITL_REVIEW", payload, expected)
        return d

    def adjudicate(self, uid: str, payload: dict, token: str, expected: int) -> dict:
        person = self.identity(token, "arbitrator")
        validate("adjudication", payload)
        scan_identifiers(payload)
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            reviewers = {r["identity"]["id"] for r in d["reviews"]}
            require(len(reviewers) >= self.cfg["review"]["minimum_reviewers"], "Independent HITL submissions required first")
            require(person["id"] not in reviewers, "Arbitrator must be distinct from reviewers")
            self.check_refs(d, payload["evidence_refs"])
            for h in payload["meanings"]:
                self.check_refs(d, h["evidence_refs"])
            require(len({h["id"] for h in payload["meanings"]}) == len(payload["meanings"]), "Distinct accepted meaning IDs required")
            require(payload["action"] not in ("approve", "multiple") or payload["meanings"], "Accepted meaning required")
            require(payload["action"] != "approve" or len(payload["meanings"]) == 1, "Use multiple to preserve several readings")
            require(payload["action"] != "multiple" or len(payload["meanings"]) >= 2, "Multiple requires at least two readings")
            self.invalidate(d, "Adjudication superseded")
            decision = {"identity": person, "decision": payload, "timestamp": now(), "reviewed_version": expected,
                "reviews_hash": digest(d["reviews"]), "models_hash": digest(d["models"]), "comparison_hash": digest(d["comparison"])}
            decision["decision_hash"] = digest(decision)
            d["adjudication"] = decision
            d["state"] = {"approve": "ADJUDICATED", "multiple": "ADJUDICATED", "request_context": "NEEDS_CONTEXT", "reject": "REJECTED", "unresolved": "UNRESOLVED"}[payload["action"]]
            if payload["risk_signal"] in self.cfg["risk"]["priority_signals"]:
                d["priority"]["queue"] = "PRIORITY"
                d["priority"]["evidence"].append(decision)
            if d["state"] == "ADJUDICATED":
                queries = sorted({s for h in payload["meanings"] for s in h["search_terms"]})
                d["terminology"] = self.resolver.for_meanings(payload["meanings"])
            self.save_action(d, person, "HUMAN_ADJUDICATION", decision, expected)
        return d

    def complete_review(self, uid: str, payload: dict, token: str, expected: int) -> dict:
        """Explicit single-reviewer decision; never manufacture independent peer reviews."""
        person = self.identity(token, "reviewer")
        require(self.cfg["review"].get("workflow") == "single_reviewer", "Single-reviewer workflow is not enabled")
        validate("guided_review", payload)
        validate("adjudication", payload["decision"])
        scan_identifiers(payload)
        decision_payload = payload["decision"]
        meanings = decision_payload["meanings"]
        ids = {h["id"] for h in meanings}
        require(len(ids) == len(meanings), "Distinct meaning IDs required")
        require(set(payload["annotations"]) == ids, "Each meaning needs category and DAP annotations")
        category_map = {k:v[1] for k,v in CATEGORY_FAMILIES.items()}
        require(decision_payload["rationale"].strip(), "Explain your meaning decision")
        for h in meanings:
            require(h["category"] == category_map[payload["annotations"][h["id"]]["family_code"]], "Category and workshop code must agree")
            require(all(h[k].strip() for k in ("meaning", "rationale", "uncertainty")), "Each meaning needs text, rationale and uncertainty")
        action = decision_payload["action"]
        require(action != "approve" or len(meanings) == 1, "Approve exactly one meaning, or retain multiple meanings")
        require(action != "multiple" or len(meanings) >= 2, "Multiple requires at least two meanings")
        require(action not in ("approve", "multiple") or payload["applicability_confirmed"], "Confirm applicability before approving meaning")
        require(not payload["second_opinion_requested"] or action == "unresolved", "Second opinion leaves meaning unresolved")
        checks = payload.get("safety_checks", [])
        # "No concern identified" stands on its own; uncertain or flagged findings need a note.
        if not payload["safety_note"].strip() and decision_payload["risk_signal"] != "not_flagged":
            raise field_error("safety_note", "Add a safety assessment note; state that assessment is pending if it has not been completed.")
        if payload["safety_note"].strip().strip(".").casefold() in EMPTY_NOTES and not checks:
            raise field_error("safety_note", "Say what you checked for safety, or tick the checks you made. A note of “none” on its own is not a safety assessment.")
        snapshot = self.store.get(uid)
        usable = {r["configuration_id"] for r in snapshot["models"] if r.get("output")}
        for model_id in payload.get("model_ratings", {}):
            if model_id not in usable:
                raise field_error("model_ratings", f"{model_id} has no usable reading to rate.")
        readings = {(r["configuration_id"], h["id"]) for r in snapshot["models"] if r.get("output") for h in r["output"]["hypotheses"]}
        for meaning_id, origin in payload.get("meaning_origins", {}).items():
            require(meaning_id in ids, "Meaning origin refers to a meaning that is not in this decision")
            require((origin["model"], origin["hypothesis_id"]) in readings, "Meaning origin must be a reading from this case's models")
        self.check_mode(snapshot)
        require(snapshot["version"] == expected, "Stale version: refresh the dossier")
        self.check_refs(snapshot, decision_payload["evidence_refs"])
        for h in meanings: self.check_refs(snapshot, h["evidence_refs"])
        started = monotonic()
        results = self.resolver.for_meanings(meanings) if action in ("approve", "multiple") else None
        lookup_seconds = round(monotonic() - started, 2)
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            require(d["version"] == expected, "Stale version: refresh the dossier")
            d["dictionary_evidence"] = d.get("dictionary_evidence") or dictionary_evidence(self.cfg, d["source"])
            if d.get("second_opinion_request"):
                require(d["second_opinion_request"]["requested_by"] != person["id"], "A second opinion must come from another reviewer")
            self.check_refs(d, decision_payload["evidence_refs"])
            for h in meanings:
                self.check_refs(d, h["evidence_refs"])
            self.invalidate(d, "Single-reviewer meaning decision superseded")
            decision = {"identity": person, "decision": decision_payload, "guided_review": {k: v for k, v in payload.items() if k != "decision"},
                "workflow": "single_reviewer", "timestamp": now(), "reviewed_version": expected,
                "reviews_hash": digest(d["reviews"]), "models_hash": digest(d["models"]), "comparison_hash": digest(d["comparison"])}
            decision["decision_hash"] = digest(decision)
            d["adjudication"] = decision
            d["second_opinion_request"] = {"requested_by": person["id"], "timestamp": now()} if payload["second_opinion_requested"] else None
            d["reviews"].append({"identity": person, "decision": {"action": action, "preferred": meanings,
                "comment": decision_payload["rationale"], "evidence_refs": decision_payload["evidence_refs"],
                "risk_signal": decision_payload["risk_signal"], "applicability_confirmed": payload["applicability_confirmed"],
                "uncertainties": [h["uncertainty"] for h in meanings]}, "timestamp": now(), "reviewed_version": expected,
                "workflow": "single_reviewer"})
            d["state"] = {"approve": "ADJUDICATED", "multiple": "ADJUDICATED", "request_context": "NEEDS_CONTEXT",
                "reject": "REJECTED", "unresolved": "UNRESOLVED"}[action]
            if decision_payload["risk_signal"] in self.cfg["risk"]["priority_signals"]:
                d["priority"]["queue"] = "PRIORITY"
                d["priority"]["evidence"].append(decision)
            if d["state"] == "ADJUDICATED":
                # Only the human-approved meaning supplies lookup terms.
                d["terminology"] = results
                d["terminology_lookup"] = {"seconds": lookup_seconds, "resources": list(RESOURCES), "timestamp": now()}
            self.save_action(d, person, "SINGLE_REVIEWER_DECISION", decision, expected)
        return d

    def refresh_terminology(self, uid: str, payload: dict, token: str, expected: int) -> dict:
        """Rerun every source, or only the sources named (for example one that failed)."""
        person = self.identity(token, "terminology")
        require(set(payload) <= {"resources"}, "Lookup uses only saved approved meaning search terms")
        resources = payload.get("resources", list(RESOURCES))
        require(isinstance(resources, list) and resources and set(resources) <= set(RESOURCES) and len(set(resources)) == len(resources),
            "Choose MFOEM, MFOMD or SNOMED_CT to rerun")
        snapshot = self.store.get(uid)
        self.check_mode(snapshot)
        require(snapshot["version"] == expected, "Stale version: refresh the dossier")
        require(snapshot["state"] == "ADJUDICATED", "Approve meaning before terminology lookup")
        started = monotonic()
        results = self.resolver.for_meanings(snapshot["adjudication"]["decision"]["meanings"], resources)
        lookup_seconds = round(monotonic() - started, 2)
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            require(d["version"] == expected, "Stale version: refresh the dossier")
            d["dictionary_evidence"] = d.get("dictionary_evidence") or dictionary_evidence(self.cfg, d["source"])
            require(d["state"] == "ADJUDICATED", "Approve meaning before terminology lookup")
            queries = sorted({s for h in d["adjudication"]["decision"]["meanings"] for s in h["search_terms"]})
            d.setdefault("dictionary_history", []).append(d.get("dictionary_evidence"))
            d["dictionary_evidence"] = dictionary_evidence(self.cfg, d["source"])
            d.setdefault("terminology_history", []).append({"version": d["version"], "terminology": d["terminology"]})
            for mapping in d["mapping_reviews"]:
                if mapping["decision"]["resource"] in resources:
                    mapping["stale"] = True
            d["terminology"] = {**d["terminology"], **results}
            d["terminology_lookup"] = {"seconds": lookup_seconds, "resources": resources, "timestamp": now()}
            self.save_action(d, person, "TERMINOLOGY_LOOKUP_REFRESHED", {"queries": queries, "resources": resources}, expected)
        return d

    def curate(self, uid: str, payload: dict, token: str, expected: int) -> dict:
        person = self.identity(token, "curator")
        validate("curation", payload)
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            require(d["state"] == "ADJUDICATED", "Meaning must be adjudicated before local curation")
            self.check_refs(d, payload["evidence_refs"])
            h = next((h for h in d["adjudication"]["decision"]["meanings"] if h["id"] == payload["meaning_id"]), None)
            require(h, "Curation must reference an accepted meaning")
            old = next((s for s in self.store.senses() if s["id"] == payload["sense_id"]), None)
            version = old["version"] + 1 if old else 1
            reusable_meaning = {k: v for k, v in h.items() if k not in ("qualifiers", "evidence_refs", "rationale", "counterevidence", "cultural_notes")}
            sense = {**payload, "id": payload["sense_id"], "version": version, "status": "APPROVED",
                "meaning": reusable_meaning, "curator": person, "origin_utterance": uid, "created_at": now(),
                "review_annotations": d["adjudication"].get("guided_review", {}).get("annotations", {}).get(h["id"]),
                "meaning_decision_hash": d["adjudication"]["decision_hash"],
                "simulated": person["simulated"] or d["mode"] == "fixture" or d["adjudication"]["identity"]["simulated"]}
            self.store.db.execute("INSERT INTO senses VALUES(?,?,?)", (sense["id"], version, canonical(sense)))
            if old:
                for dependent in self.store.all():
                    if dependent["source"]["utterance_id"] == uid:
                        continue
                    affected = False
                    for link in dependent["sense_links"]:
                        if link["id"] == sense["id"]:
                            link["stale"] = True
                            affected = True
                    for mapping in dependent["mapping_reviews"]:
                        if mapping["decision"]["sense_id"] == sense["id"]:
                            mapping["stale"] = True
                            affected = True
                    if affected:
                        self.save_action(dependent, person, "DEPENDENT_SENSE_STALE", {"sense_id": sense["id"], "new_version": version}, dependent["version"])
            d["sense_links"] = [s for s in d["sense_links"] if s["id"] != sense["id"]] + [{"id": sense["id"], "version": version, "meaning_id": h["id"]}]
            for mapping in d["mapping_reviews"]:
                if mapping["decision"]["sense_id"] == sense["id"]:
                    mapping["stale"] = True
            self.save_action(d, person, "LOCAL_CONCEPT_CURATION", sense, expected)
        return d

    def mapping(self, uid: str, payload: dict, token: str, expected: int) -> dict:
        person = self.identity(token, "terminology")
        validate("mapping", payload)
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            require(d["state"] == "ADJUDICATED", "Unresolved meaning blocks mapping review")
            self.check_refs(d, payload["evidence_refs"])
            lookup = d["terminology"][payload["resource"]]
            if payload["action"] == "gap":
                require(lookup["state"] in ("HITS", "NO_RESULTS"), "Retrieval failure is not a semantic gap")
            sense = next((s for s in self.store.senses() if s["id"] == payload["sense_id"]), None)
            if lookup.get("by_meaning"):
                link = next((s for s in d["sense_links"] if s["id"] == payload["sense_id"] and not s.get("stale")), None)
                require(link, "Select a local concept linked to the meaning being reviewed")
                lookup = lookup["by_meaning"].get(link["meaning_id"])
                require(lookup, "No terminology lookup recorded for this meaning; rerun lookup")
            candidate = None
            if payload["candidate_id"]:
                candidate = next((c for c in lookup["candidates"] if c["id"] == payload["candidate_id"]), None)
                require(candidate, "Identifier was not retrieved for this adjudication")
                verified = self.resolver.verify(payload["resource"], candidate["id"], candidate["iri"])
                require(verified["release"] == candidate["release"], "Release changed: retrieve and review again")
                require(payload["action"] != "approve" or verified["active"], "Inactive concept cannot be approved")
            if payload["action"] == "approve":
                require(candidate and payload["predicate"], "Verified candidate and directed predicate required")
                require(sense and self.sense_current(sense), "Curated current local sense required")
                require(any(s["id"] == sense["id"] and s["version"] == sense["version"] for s in d["sense_links"]), "Sense not linked to this adjudication")
            if payload["action"] == "gap":
                require(lookup["state"] in ("HITS", "NO_RESULTS"), "Retrieval failure is not a semantic gap")
                require(all(c.get("total_reported") is not None and c["returned"] >= c["total_reported"] for c in lookup.get("search_coverage", [])), "Search incomplete: narrow capped terms and rerun, or defer; a gap cannot be recorded")
                require(not payload["candidate_id"] and payload["predicate"] is None, "Gap is a separate record, not a target mapping")
            decision = {"identity": person, "decision": payload, "candidate": candidate, "timestamp": now(),
                "reviewed_version": expected, "sense_version": sense["version"] if sense else None,
                "meaning_decision_hash": d["adjudication"]["decision_hash"], "resource_metadata": lookup.get("metadata"),
                "stale": False}
            # Superseding decisions are retained but marked stale, including gap/rejection corrections.
            for previous in d["mapping_reviews"]:
                if (previous["decision"]["resource"], previous["decision"]["sense_id"], previous["decision"]["candidate_id"]) == (payload["resource"], payload["sense_id"], payload["candidate_id"]):
                    previous["stale"] = True
            d["mapping_reviews"].append(decision)
            if payload["action"] in ("challenge_meaning", "contest"):
                self.invalidate(d, "Terminology reviewer challenges meaning or contested relationship")
            self.save_action(d, person, "MAPPING_REVIEW", decision, expected)
        return d

    def signoff(self, uid: str, payload: dict, token: str, expected: int) -> dict:
        """One atomic request, retaining an audit event for every source decision."""
        from .intake import IntakeError
        self.identity(token, "terminology")
        require(set(payload) == {"concept", "decisions"}, "Supply local concept and three source decisions")
        decisions = payload["decisions"]
        require(isinstance(decisions, list) and len(decisions) == 3 and
                {d.get("resource") for d in decisions} == {"MFOEM", "MFOMD", "SNOMED_CT"},
                "Sign off each of the three sources exactly once")
        require(all(d.get("action") in ("approve", "gap", "unresolved", "reject") for d in decisions),
                "Use the separate meaning review to reopen or challenge a meaning")
        require(len({d.get("sense_id") for d in decisions}) == 1, "Sign off one meaning at a time")
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            require(d["version"] == expected, "Stale version: refresh the dossier")
            concept = payload["concept"]
            if concept is not None:
                require(all(x["sense_id"] == concept["sense_id"] for x in decisions), "Concept and sign-off must agree")
                d = self.curate(uid, concept, token, d["version"])
            require(any(s["id"] == decisions[0]["sense_id"] and not s.get("stale") for s in d["sense_links"]), "Save a current local concept for this meaning")
            for decision in decisions:
                try:
                    d = self.mapping(uid, decision, token, d["version"])
                except (ValueError, KeyError) as exc:
                    raise IntakeError("signoff_" + decision["resource"], str(exc)) from exc
        return d

    def flag_case(self, uid: str, payload: dict, token: str, expected: int) -> dict:
        """Mark a case as active, a test case or withdrawn. Nothing is deleted; decisions are untouched."""
        person = self.identity(token, "reviewer")
        require(set(payload) == {"status", "reason"}, "Supply a case status and a reason")
        if payload["status"] not in CASE_STATUSES:
            raise field_error("case_status", "Choose active, test or withdrawn.")
        if not isinstance(payload["reason"], str) or not payload["reason"].strip():
            raise field_error("case_reason", "Say why the case status is changing.")
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            require(d["version"] == expected, "Stale version: refresh the dossier")
            previous = (d.get("case_flag") or {}).get("status", "active")
            require(previous != payload["status"], "The case already has this status")
            d["case_flag"] = {"status": payload["status"], "reason": payload["reason"].strip(), "previous": previous,
                "identity": person["id"], "timestamp": now()}
            self.save_action(d, person, "CASE_STATUS_CHANGED", d["case_flag"], expected)
        return d

    def add_evidence(self, uid: str, payload: dict, token: str, expected: int):
        person = self.identity(token)
        require(set(payload) == {"id", "text", "reference"} and all(isinstance(v, str) and v for v in payload.values()), "Evidence needs id/text/reference")
        scan_identifiers(payload)
        with self.store.transaction():
            d = self.store.get(uid)
            self.check_mode(d)
            require(payload["id"] not in {e["id"] for e in d["source"]["evidence"] + d["external_evidence"]}, "Evidence ID already exists")
            d["external_evidence"].append(payload)
            self.invalidate(d, "New external evidence requires human reassessment")
            self.save_action(d, person, "EVIDENCE_ADDED", payload, expected)
        return d

    def view(self, uid: str, token: str) -> dict:
        person = self.identity(token)
        d = self.store.get(uid)
        # Reading a case must not invent a new dictionary run for historical records.
        d.setdefault("dictionary_evidence", None)
        d["workflow_steps"] = workflow_steps(d)
        d["progress"] = case_progress(d)
        if self.cfg["review"].get("workflow") != "single_reviewer" and "reviewer" in person["roles"] and not any(r["identity"]["id"] == person["id"] for r in d["reviews"]):
            # Preserve independent first submissions before showing peers' decisions.
            d["reviews"] = []
            d["adjudication"] = None
            d["mapping_reviews"] = []
            d["stale_artifacts"] = []
            d["priority"]["evidence"] = [e for e in d["priority"]["evidence"] if "identity" not in e]
            d["independent_review_notice"] = "Peer submissions hidden until your first submission"
        return d
