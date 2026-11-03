from __future__ import annotations

import json
import os
import time
from typing import TypedDict, Any

from . import network
from .common import ROOT, canonical, digest, evidence_check, now, require, resolve, validate


class ModelRun(TypedDict):
    configuration_id: str
    status: str
    attempts: list[dict]
    output: dict | None
    provenance: dict
    runtime_seconds: float


def validate_output(data: dict, source: dict):
    validate("model_output", data)
    ids = [h["id"] for h in data["hypotheses"]]
    require(len(ids) == len(set(ids)), "Duplicate hypothesis IDs")
    require(data["primary_hypothesis"] is None or data["primary_hypothesis"] in ids, "Primary must reference a hypothesis")
    evidence_check(data["risk"]["evidence_refs"], source)
    for h in data["hypotheses"]:
        evidence_check(h["evidence_refs"], source)
        for note in h["cultural_notes"]:
            try:
                evidence_check([note["reference"]], source)
            except ValueError:
                raise ValueError(f"Cultural note {note['id']}: reference must name supplied evidence ({', '.join(e['id'] for e in source['evidence'])})") from None
        require(not any(__import__("re").search(r"(?:SNOMED|SCTID|MFOEM|MFOMD)[:_ ]\d+", s, __import__("re").I)
                        for s in h["search_terms"]), "Models propose search terms, not authoritative identifiers")


def call(cfg: dict, model: dict, messages: list[dict], source: dict, attempt: int) -> tuple[str, dict]:
    provider = model["provider"]
    if provider == "fixture":
        require(cfg["mode"] == "fixture", "Fixture providers forbidden in real modes")
        fixture = json.loads(resolve(cfg, cfg["fixtures"]).read_text())[source["utterance_id"]][model["id"]]
        response = fixture[min(attempt, len(fixture) - 1)]
        if isinstance(response, dict) and "fixture_failure" in response:
            raise RuntimeError("Fixture model unavailable")
        return response if isinstance(response, str) else canonical(response), {"actual_model": "SIMULATED:" + model["id"], "digest": digest(fixture)}
    require(cfg["mode"] != "fixture", "OFFLINE: only fixture models permitted")
    endpoint = model["endpoint"].rstrip("/")
    if provider == "ollama":
        # Missing model stays a visible failure. Never pull or substitute models.
        installed = network.request(cfg, endpoint + "/api/tags")
        match = next((m for m in installed.get("models", []) if model["model"] in (m.get("name"), m.get("model"))), None)
        require(match, "Configured Ollama model unavailable")
        response = network.request(cfg, endpoint + "/api/chat", {"model": model["model"], "messages": messages,
                    "stream": False, "format": json.loads((ROOT / "schemas/model_output.json").read_text()), "options": model["settings"], "keep_alive": 0})
        return response["message"]["content"], {"actual_model": response.get("model"), "digest": match.get("digest")}
    require(provider == "openai_compatible" and cfg["mode"] == "connected", "Unknown/unauthorized provider")
    key = os.environ.get(model["key_env"])
    require(key, "API credential missing")
    response = network.request(cfg, endpoint + "/chat/completions", {"model": model["model"], "messages": messages,
        "response_format": {"type": "json_object"}, **model["settings"]}, key)
    return response["choices"][0]["message"]["content"], {"actual_model": response.get("model"),
        "digest": None, "system_fingerprint": response.get("system_fingerprint")}


def interpret(cfg: dict, source: dict, progress=None) -> list[ModelRun]:
    prompt = resolve(cfg, cfg["prompt"]).read_text()
    schema = json.loads((ROOT / "schemas/model_output.json").read_text())
    authorized_input = {"source": source, "output_schema": schema}
    initial_messages = [{"role": "system", "content": prompt}, {"role": "user", "content": canonical(authorized_input)}]
    emit = progress or (lambda event: None)
    results = []
    for model in cfg["models"]:  # sequential by design; no cross-model shared completion
        started = time.monotonic()
        emit({"stage": "model_started", "model": model["id"]})
        provenance = {"provider": model["provider"], "requested_model": model["model"], "settings": model["settings"],
            "prompt_hash": digest(prompt), "input_hash": digest(authorized_input), "config_hash": digest(cfg),
            "started_at": now(), "reference_versions": [],
            "cache_key": digest([authorized_input, model, prompt, cfg]), "cache_used": False}
        result: ModelRun = {"configuration_id": model["id"], "status": "FAILED", "attempts": [], "output": None,
                           "provenance": provenance, "runtime_seconds": 0.0}
        messages = list(initial_messages)
        for attempt in range(2):
            try:
                raw, actual = call(cfg, model, messages, source, attempt)
                provenance.update(actual)
            except Exception as exc:
                # Error class is enough for logs; server exceptions may contain secrets.
                result["attempts"].append({"timestamp": now(), "error": type(exc).__name__, "failure": "MODEL_UNAVAILABLE_OR_REQUEST_FAILED"})
                result["failure_reason"] = "Model could not be reached or the request was rejected."
                break
            item = {"timestamp": now(), "raw": raw}
            result["attempts"].append(item)
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and ("source" in parsed or "original_text" in parsed) and "hypotheses" not in parsed:
                    raise ValueError("Model returned its input instead of a reading")
                validate_output(parsed, source)
            except (ValueError, KeyError, TypeError, __import__("jsonschema").ValidationError) as exc:
                # Validation messages are fed only back to this same model, never other models.
                error = str(exc)[:2000]
                item["validation_error"] = error
                result["failure_reason"] = ("Reply was not valid JSON." if isinstance(exc, json.JSONDecodeError) else
                    "Model returned its input instead of a reading." if "returned its input" in error else
                    "Reply did not match the output schema: " + error.splitlines()[0][:300] if isinstance(exc, __import__("jsonschema").ValidationError) else
                    "Reply failed evidence or consistency validation: " + error.splitlines()[0][:300])
                messages = initial_messages + [{"role": "assistant", "content": raw},
                    {"role": "user", "content": "One retry. Correct JSON, schema or evidence/consistency validation errors: " + error}]
                continue
            result.pop("failure_reason", None)
            result["output"] = parsed
            result["status"] = "ABSTAINED" if parsed["primary_hypothesis"] is None else "COMPLETED"
            break
        result["runtime_seconds"] = time.monotonic() - started
        provenance["finished_at"] = now()
        emit({"stage": "model_finished", "model": model["id"], "seconds": round(result["runtime_seconds"], 2), "outcome": result["status"], "reason": result.get("failure_reason"),
              "confidence": result["output"]["confidence_uncalibrated"] if result["output"] else None})
        results.append(result)
    return results
