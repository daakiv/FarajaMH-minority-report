# Repository tree and responsibilities

> **Scope: earlier prototype / historical evidence.** The [v9.1 infographic](WORKFLOW.md) now defines the process. This document does not prove that process is implemented. See [ALIGNMENT.md](ALIGNMENT.md) for conflicts and missing features. The approach is not yet adopted by FarajaMH and testing is dummy-data only.

Every delivered source/config/prompt/schema/test/document is listed below. `.venv/` and `work/` are local runtime state. Generated acceptance artifacts are summarized after the source inventory.

```text
.gitignore
README.md
config.yaml
docs/ACCEPTANCE.md
docs/ARCHITECTURE.md
docs/COMMANDS.md
docs/PILOT.md
docs/REPOSITORY.md
docs/SETUP.md
examples/arbitrator.json
examples/curation.json
examples/mapping.json
examples/new-evidence.json
examples/reviewer.json
examples/source.json
farajamh/__init__.py
farajamh/__main__.py
farajamh/agreement.py
farajamh/cli.py
farajamh/common.py
farajamh/exports.py
farajamh/models.py
farajamh/network.py
farajamh/pilot.py
farajamh/pipeline.py
farajamh/prompts/interpret-v1.md
farajamh/reporting.py
farajamh/schemas/adjudication.json
farajamh/schemas/croissant-context-1.0.json
farajamh/schemas/curation.json
farajamh/schemas/hypothesis.json
farajamh/schemas/manifest.json
farajamh/schemas/mapping.json
farajamh/schemas/model_output.json
farajamh/schemas/review.json
farajamh/schemas/source.json
farajamh/storage.py
farajamh/templates/review.html
farajamh/terminology.py
farajamh/webapp.py
pilot/expected.json
pilot/manifest.json
pilot/model_responses.json
pilot/utterances.jsonl
pyproject.toml
requirements.lock
tests/conftest.py
tests/test_exports_pilot_ui.py
tests/test_governance.py
tests/test_interpretation.py
tests/test_terminology.py
tools/build_inventory.py
tools/build_pilot.py
tools/build_schemas.py
tools/validate_upstream.py
validation-requirements.lock
```

| File | Responsibility |
|---|---|
| `.gitignore` | Exclude licensed inputs, secrets and local runtime state |
| `README.md` | Ordered deliverables and quick start |
| `config.yaml` | One complete commented configuration: modes, models, mandatory terminology, risk, roles and exports |
| `docs/ACCEPTANCE.md` | Executed validation, assumptions, blockers and known limitations |
| `docs/ARCHITECTURE.md` | Modules, diagram, source evidence and figure alignment |
| `docs/COMMANDS.md` | Exact commands, arguments, modes and transitions |
| `docs/PILOT.md` | Synthetic scenarios, measured fixture metrics and denominators |
| `docs/REPOSITORY.md` | Every delivered source/config/test file and responsibility |
| `docs/SETUP.md` | Environment, models, hardware estimates, authorized resources and identity setup |
| `examples/arbitrator.json` | Explicit SIMULATED CLI example: arbitrator |
| `examples/curation.json` | Explicit SIMULATED CLI example: curation |
| `examples/mapping.json` | Explicit SIMULATED CLI example: mapping |
| `examples/new-evidence.json` | Explicit SIMULATED CLI example: new-evidence |
| `examples/reviewer.json` | Explicit SIMULATED CLI example: reviewer |
| `examples/source.json` | Explicit SIMULATED CLI example: source |
| `farajamh/__init__.py` | Package identity and version |
| `farajamh/__main__.py` | Module CLI entry point |
| `farajamh/agreement.py` | Contextual grouping, primary votes, dissent and Fleiss kappa |
| `farajamh/cli.py` | All command parsing and dispatch |
| `farajamh/common.py` | Configuration, schema/evidence validation, hashing and input guards |
| `farajamh/exports.py` | Dossiers/review CSV/XLSX, approved SSSOM, assertions, Croissant and validators |
| `farajamh/models.py` | Independent fixture/Ollama/OpenAI-compatible calls, retries and trusted provenance |
| `farajamh/network.py` | Mode and endpoint allowlist; no redirects or fixture requests |
| `farajamh/pilot.py` | Explicit simulated decisions and network-blocked full pilot |
| `farajamh/pipeline.py` | Authenticated review, arbitration, curation, mapping, CKB and stale-state transitions |
| `farajamh/prompts/interpret-v1.md` | Versioned Kiswahili-aware independent interpretation prompt |
| `farajamh/prompts/interpret-v2.md` | v1 plus a request for numeric uncalibrated confidence; used by `config.live-test.yaml` |
| `farajamh/reporting.py` | Metrics, denominators and report artifacts |
| `farajamh/schemas/adjudication.json` | Version 1 JSON Schema for adjudication |
| `farajamh/schemas/croissant-context-1.0.json` | Pinned Croissant 1.0 inline context from mlcroissant 1.0.22 |
| `farajamh/schemas/curation.json` | Version 1 JSON Schema for curation |
| `farajamh/schemas/hypothesis.json` | Version 1 JSON Schema for hypothesis |
| `farajamh/schemas/manifest.json` | Version 1 JSON Schema for manifest |
| `farajamh/schemas/mapping.json` | Version 1 JSON Schema for mapping |
| `farajamh/schemas/model_output.json` | Version 1 JSON Schema for model output |
| `farajamh/schemas/review.json` | Version 1 JSON Schema for review |
| `farajamh/schemas/source.json` | Version 1 JSON Schema for source |
| `farajamh/storage.py` | SQLite source/revision/sense/audit persistence with append-only triggers |
| `farajamh/templates/review.html` | Review UI: source, readings, votes, evidence and persistent structured decision forms |
| `farajamh/terminology.py` | OLS, OWL and RF2 import/search/verification |
| `farajamh/webapp.py` | Loopback persistent HTTP review application |
| `pilot/expected.json` | Expected vote state per pilot utterance |
| `pilot/manifest.json` | Synthetic dataset manifest; count/guard/validation disclaimer |
| `pilot/model_responses.json` | Deterministic four-configuration responses, failures and retry fixtures |
| `pilot/utterances.jsonl` | Twenty immutable synthetic contextual input records |
| `pyproject.toml` | Python package metadata, pinned direct dependencies and console entry point |
| `requirements.lock` | Exact exercised core dependency closure |
| `tests/conftest.py` | Isolated storage/config fixtures and decision helpers |
| `tests/test_exports_pilot_ui.py` | SSSOM/Croissant, complete pilot, review packages and authenticated HTTP persistence |
| `tests/test_governance.py` | Roles, decisions, stale artifacts, CKB, mapping/release gates |
| `tests/test_interpretation.py` | Schemas, votes, risk, independence, adapter contracts and network guards |
| `tests/test_terminology.py` | Generated RF2/OWL and mocked OLS integration tests |
| `tools/build_inventory.py` | Generate this inventory and artifact checksums |
| `tools/build_pilot.py` | Reproducible twenty-input and four-model fixture generation |
| `tools/build_schemas.py` | Reproducible JSON Schema generation |
| `tools/validate_upstream.py` | Pinned official SSSOM model/Croissant validation with network blocked |
| `validation-requirements.lock` | Exact optional upstream-validator environment (tested Python 3.13/macOS) |

`evidence/pilot-final/` contains the SQLite pilot database, run manifest, simulated decision file, review package, four output types and per-item dossiers; see `COMMANDS.md` for its tree. `evidence/tests-final.xml`, `evidence/upstream-validation-final.json`, `evidence/fixture-preflight.json`, `evidence/review-ui.jpg` and `evidence/acceptance-manifest.json` record the verification outputs. Earlier development pilot directories are retained as historical snapshots.

`evidence/acceptance-manifest.json` enumerates all delivered source and evidence files with SHA-256 checksums, excluding itself and mutable SQLite sidecars. It is a reproducibility inventory, not cryptographic proof against modification.
