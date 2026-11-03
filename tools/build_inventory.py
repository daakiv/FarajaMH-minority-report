"""Generate the source/config/test inventory and SHA-256 manifest for delivered artifacts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".venv", "work", "__pycache__", ".pytest_cache", "farajamh_cultural_interpretation_pipeline.egg-info"}
RESPONSIBILITY = {
    "__init__.py": "Package identity and version", "__main__.py": "Module CLI entry point", "common.py": "Configuration, schema/evidence validation, hashing and input guards",
    "storage.py": "SQLite source/revision/sense/audit persistence with append-only triggers", "network.py": "Mode and endpoint allowlist; no redirects or fixture requests",
    "models.py": "Independent fixture/Ollama/OpenAI-compatible calls, retries and trusted provenance", "agreement.py": "Contextual grouping, primary votes, dissent and Fleiss kappa",
    "pipeline.py": "Authenticated review, arbitration, curation, mapping, CKB and stale-state transitions", "terminology.py": "OLS, OWL and RF2 import/search/verification",
    "exports.py": "Dossiers/review CSV/XLSX, approved SSSOM, assertions, Croissant and validators", "reporting.py": "Metrics, denominators and report artifacts",
    "pilot.py": "Explicit simulated decisions and network-blocked full pilot", "cli.py": "All command parsing and dispatch", "webapp.py": "Loopback persistent HTTP review application",
    "review.html": "Review UI: source, readings, votes, evidence and persistent structured decision forms",
    "conftest.py": "Isolated storage/config fixtures and decision helpers", "test_interpretation.py": "Schemas, votes, risk, independence, adapter contracts and network guards",
    "test_governance.py": "Roles, decisions, stale artifacts, CKB, mapping/release gates", "test_terminology.py": "Generated RF2/OWL and mocked OLS integration tests",
    "test_exports_pilot_ui.py": "SSSOM/Croissant, complete pilot, review packages and authenticated HTTP persistence",
    "build_schemas.py": "Reproducible JSON Schema generation", "build_pilot.py": "Reproducible twenty-input and four-model fixture generation",
    "validate_upstream.py": "Pinned official SSSOM model/Croissant validation with network blocked", "build_inventory.py": "Generate this inventory and artifact checksums",
    "config.yaml": "One complete commented configuration: modes, models, mandatory terminology, risk, roles and exports",
    "pyproject.toml": "Python package metadata, pinned direct dependencies and console entry point",
    "requirements.lock": "Exact exercised core dependency closure", "validation-requirements.lock": "Exact optional upstream-validator environment (tested Python 3.13/macOS)",
    ".gitignore": "Exclude licensed inputs, secrets and local runtime state", "README.md": "Ordered deliverables and quick start",
    "ARCHITECTURE.md": "Modules, diagram, source evidence and figure alignment", "COMMANDS.md": "Exact commands, arguments, modes and transitions",
    "SETUP.md": "Environment, models, hardware estimates, authorized resources and identity setup", "PILOT.md": "Synthetic scenarios, measured fixture metrics and denominators",
    "ACCEPTANCE.md": "Executed validation, assumptions, blockers and known limitations", "REPOSITORY.md": "Every delivered source/config/test file and responsibility",
}


def describe(path):
    if path.name in RESPONSIBILITY: return RESPONSIBILITY[path.name]
    if "schemas" in path.parts:
        return "Pinned Croissant 1.0 inline context from mlcroissant 1.0.22" if "context" in path.name else "Version 1 JSON Schema for " + path.stem.replace("_", " ")
    if "prompts" in path.parts: return "Versioned Kiswahili-aware independent interpretation prompt"
    if "examples" in path.parts: return "Explicit SIMULATED CLI example: " + path.stem
    if "pilot" in path.parts: return {"manifest.json": "Synthetic dataset manifest; count/guard/validation disclaimer", "utterances.jsonl": "Twenty immutable synthetic contextual input records", "model_responses.json": "Deterministic four-configuration responses, failures and retry fixtures", "expected.json": "Expected vote state per pilot utterance"}.get(path.name, "Pilot fixture")
    return "Delivered project artifact"


def main():
    destination = ROOT / "docs/REPOSITORY.md"
    destination.touch(exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and not any(x in EXCLUDED for x in p.relative_to(ROOT).parts)
                   and "evidence" not in p.relative_to(ROOT).parts)
    lines = ["# Repository tree and responsibilities", "", "Every delivered source/config/prompt/schema/test/document is listed below. `.venv/` and `work/` are local runtime state. Generated acceptance artifacts are summarized after the source inventory.", "", "```text"]
    lines += [str(p.relative_to(ROOT)) for p in files]
    lines += ["```", "", "| File | Responsibility |", "|---|---|"]
    lines += [f"| `{p.relative_to(ROOT)}` | {describe(p.relative_to(ROOT))} |" for p in files]
    lines += ["", "`evidence/pilot-final/` contains the SQLite pilot database, run manifest, simulated decision file, review package, four output types and per-item dossiers; see `COMMANDS.md` for its tree. `evidence/tests-final.xml`, `evidence/upstream-validation-final.json`, `evidence/fixture-preflight.json`, `evidence/review-ui.jpg` and `evidence/acceptance-manifest.json` record the verification outputs. Earlier development pilot directories are retained as historical snapshots.", "", "`evidence/acceptance-manifest.json` enumerates all delivered source and evidence files with SHA-256 checksums, excluding itself and mutable SQLite sidecars. It is a reproducibility inventory, not cryptographic proof against modification.", ""]
    destination.write_text("\n".join(lines))
    artifacts = sorted(p for p in ROOT.rglob("*") if p.is_file() and not any(x in EXCLUDED for x in p.relative_to(ROOT).parts)
        and p.name != "acceptance-manifest.json" and not p.name.endswith(("-wal", "-shm")))
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}
    (ROOT / "evidence/acceptance-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Inventoried {len(files)} source/config/test/document files and {len(manifest)} total artifacts")


if __name__ == "__main__": main()
