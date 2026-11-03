"""Rebuild the checked-in JSON Schemas. Python stdlib only."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "farajamh" / "schemas"
OUT.mkdir(parents=True, exist_ok=True)
FAMILIES = json.loads((OUT.parent / "resources/categories.json").read_text())
S = {"type": "string", "minLength": 1}
N = {"type": ["string", "null"]}
B = {"type": "boolean"}
def arr(item=S, minimum=0): return {"type": "array", "items": item, "minItems": minimum}
def enum(*items): return {"enum": list(items)}
def obj(props, optional=()):
    return {"type": "object", "properties": props, "required": [k for k in props if k not in optional], "additionalProperties": False}
def save(name, schema):
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"urn:farajamh:schema:{name}:1", **schema}
    (OUT / (name + ".json")).write_text(json.dumps(schema, indent=2) + "\n")

qualifiers = obj({"experiencer": S, "assertion": enum("affirmed", "negated", "uncertain", "unknown"),
    "attribution": S, "event_time": S, "utterance_time": S, "setting": S})
evidence = obj({"id": S, "text": S, "reference": S})
source = obj({"schema_version": {"const": "1.0"}, "utterance_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$"},
    "synthetic": {"const": True}, "original_text": S, "language": S,
    "language_spans": arr(obj({"start": {"type": "integer", "minimum": 0}, "end": {"type": "integer", "minimum": 1},
        "language": S, "status": enum("supplied", "hypothesis", "reviewed")})),
    "source_type": S, "speaker_role": S, "speaker_ref": {"type": "string", "pattern": "^SYN-"},
    "region_variety": N, "conversation": S, "qualifiers": qualifiers, "evidence": arr(evidence, 1)})
source["properties"]["expression_span"] = {'type': 'object', 'additionalProperties': False, 'required': ['start', 'end', 'text'], 'properties': {'start': {'type': 'integer', 'minimum': 0}, 'end': {'type': 'integer', 'minimum': 1}, 'text': {'type': 'string', 'minLength': 1}}}
source["properties"]["parent_utterance_id"] = S
save("source", source)
hypothesis = obj({"id": S, "meaning": S, "category": enum(*dict.fromkeys(v[1] for v in FAMILIES.values())),
    "semantic_frame": obj({"experience": S, "cause": S, "cultural_reading": S}),
    "qualifiers": qualifiers, "search_terms": arr(S, 1), "evidence_refs": arr(S, 1), "rationale": S,
    "counterevidence": arr(), "uncertainty": S, "cultural_notes": arr(evidence)})
save("hypothesis", hypothesis)
save("model_output", obj({"schema_version": {"const": "1.0"}, "literal_gloss": S, "contextual_rendering": S,
    "hypotheses": arr(hypothesis), "primary_hypothesis": N,
    "risk": obj({"signal": enum("flagged", "not_flagged", "uncertain"), "evidence_refs": arr(S, 1), "rationale": S}),
    "questions": arr(), "confidence_uncalibrated": {"type": ["number", "null"], "minimum": 0, "maximum": 1}}))
save("review", obj({"action": enum("accept", "minority", "alternative", "multiple", "request_context", "reject", "unresolved", "confirm_ckb"),
    "preferred": arr(hypothesis), "comment": S, "evidence_refs": arr(S, 1), "uncertainties": arr(),
    "risk_signal": enum("flagged", "not_flagged", "uncertain"), "applicability_confirmed": B}))
save("adjudication", obj({"action": enum("approve", "multiple", "request_context", "reject", "unresolved"),
    "meanings": arr(hypothesis), "rationale": S, "evidence_refs": arr(S, 1), "risk_signal": enum("flagged", "not_flagged", "uncertain")}))
save("curation", obj({"sense_id": {"type": "string", "pattern": "^FARAJA:[A-Za-z0-9_-]+$"},
    "meaning_id": S, "source_label": S, "english_gloss": S, "definition": S, "synonyms": arr(),
    "cultural_applicability": S, "example_refs": arr(S, 1), "evidence_refs": arr(S, 1), "owner": S,
    "reuse_approved": B, "applicability": obj({"language": S, "region_variety": N, "conversation": S,
        "assertion": S, "attribution": S, "temporal_scope": enum("present", "past", "future", "unknown"), "setting": S})}))
save("mapping", obj({"resource": enum("MFOEM", "MFOMD", "SNOMED_CT"),
    "action": enum("approve", "reject", "gap", "unresolved", "contest", "challenge_meaning"),
    "sense_id": S, "candidate_id": N,
    "predicate": enum(None, "skos:exactMatch", "skos:closeMatch", "skos:broadMatch", "skos:narrowMatch", "skos:relatedMatch"),
    "rationale": S, "evidence_refs": arr(S, 1)}))
save("manifest", obj({"schema_version": {"const": "1.0"}, "synthetic": {"const": True}, "dataset": S,
    "count": {"type": "integer", "minimum": 1}, "description": S, "community_validated": {"const": False}}))
