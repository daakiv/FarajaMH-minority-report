# Commands and state requirements

> **Scope: earlier prototype / historical evidence.** The [v9.1 infographic](WORKFLOW.md) now defines the process. This document does not prove that process is implemented. See [ALIGNMENT.md](ALIGNMENT.md) for conflicts and missing features. The approach is not yet adopted by FarajaMH and testing is dummy-data only.

Run from `/Users/davidamadi/Documents/Projects/farajamh-cultural-interpretation-pipeline`. All commands accept global `--config PATH` **before** the subcommand. Relative configuration paths resolve against that YAML file; CLI file paths resolve against the current working directory. `python -m farajamh` is equivalent to the installed `farajamh` entry point.

## Initialization and independent interpretation

```sh
.venv/bin/python -m farajamh init
.venv/bin/python -m farajamh preflight
.venv/bin/python -m farajamh run examples/source.json
.venv/bin/python -m farajamh batch pilot/utterances.jsonl --manifest pilot/manifest.json
```

`init` creates storage/tables. Fixture `preflight` verifies fictional adapters only; a real configuration must pass actual release prerequisites. `run` accepts one JSON record; `batch` accepts JSONL plus a `synthetic: true` manifest with a matching count. Both persist source, model attempts, votes and provenance, ending in `AWAITING_REVIEW`. Reusing an existing immutable utterance ID is rejected; do not run `run` and `batch` on the same IDs in the same store unless intentionally testing that rejection.

## Deterministic offline pilot

```sh
.venv/bin/python -m farajamh dry-run --out work/pilot-new
.venv/bin/python -m farajamh validate sssom work/pilot-new/SIMULATED-artifacts/SIMULATED.mappings.sssom.tsv
.venv/bin/python -m farajamh validate catalog work/pilot-new/SIMULATED-artifacts/catalog.jsonld
```

The directory must not already exist. `dry-run` uses a separate SQLite database inside it, blocks network, runs all twenty inputs and explicitly simulated reviews/arbitration/curation, and writes four distinct artifact types. SYN01 preserves two meanings after the 2–2 split; SYN02 illustrates a minority selection; SYN03 remains unresolved and SYN17 requests context. No human-reviewed research release is produced.

```text
work/pilot-new/
  pilot.sqlite                    persistent versions, source, audit, senses
  run-manifest.json                synthetic/simulation/mode/configuration flags
  SIMULATED-decisions.json         every simulated approval payload
  review-package/                  SYN01 dossier + CSV + XLSX
  SIMULATED-artifacts/
    SIMULATED.mappings.sssom.tsv   three approved fictional concept relationships
    mapping-provenance.json        linked workflow details by TSV row
    ckb.json                       explicitly curated reusable senses
    contextual-assertions.json    current utterance facts, sense links, no OMOP IDs
    unresolved-and-gaps.json       unresolved decisions and scoped gaps
    approved-synthetic.csv        adjudicated synthetic subset only
    approved-mappings.csv         catalog-readable mapping table
    catalog.jsonld                Croissant 1.0; relative files and SHA-256
  report/
    metrics.json
    audit.json
    dossiers/SYN01.json ... SYN20.json
```

For optional pinned upstream validation (separate from the small core runtime):

```sh
.venv/bin/python -m pip install -r validation-requirements.lock
.venv/bin/python tools/validate_upstream.py work/pilot-new/SIMULATED-artifacts
```

This constructs the official SSSOM 1.0.0 mapping model, parses the catalog using mlcroissant 1.0.22 and iterates both CSV recordsets with network blocked. Local profile validation also checks CURIE completeness, required fields, current release permissions at export, JSON-LD, file references and checksums.

## Persistent review interface

Set distinct tokens in the environment that starts the review server. These are **simulation accounts** in the reference YAML. Use suitably long locally chosen values; examples below intentionally contain placeholders.

```sh
export FARAJA_DEMO_KE_TOKEN='REPLACE_WITH_LONG_TOKEN_ONE'
export FARAJA_DEMO_TZ_TOKEN='REPLACE_WITH_LONG_TOKEN_TWO'
export FARAJA_DEMO_ARBITRATOR_TOKEN='REPLACE_WITH_LONG_TOKEN_THREE'
export FARAJA_DEMO_CURATOR_TOKEN='REPLACE_WITH_LONG_TOKEN_FOUR'
.venv/bin/python -m farajamh review --serve --port 8765
```

Open `http://127.0.0.1:8765`. Enter the corresponding identity token; token values are not stored in browser localStorage or server audit records. Select a queue item. All source/model/grouping/evidence data are visible. Select any proposed hypotheses, choose a stage, and press **Prepare an empty decision form**. Selective copying happens only on this user action; nothing preselects the majority for approval. Fill the JSON decision including rationale and evidence references, then persist it. Schema errors leave the dossier unchanged.

Review actions: `accept`, `minority`, `alternative`, `multiple`, `request_context`, `reject`, `unresolved`, `confirm_ckb`. `preferred` contains full hypothesis objects; alternate interpretations use the same `hypothesis.json` schema. For a known CKB entry, submit a hypothesis instantiated with the **current** utterance qualifiers and evidence, and set `applicability_confirmed: true`; the prototype still requires arbitrator sign-off. All minority and secondary readings remain available in model details.

Arbitrator actions: `approve` (one meaning), `multiple` (two or more), `request_context`, `reject`, `unresolved`. Before sign-off, at least two distinct reviewer identities must have submitted. Peer decisions are hidden before a reviewer's initial independent submission. An arbitrator uses a distinct configured identity and sees the reviews and all model records. Submission includes the exact current dossier version; stale concurrent submissions are rejected.

## CLI review and arbitration

`--token-env` specifies the environment variable holding the same token configured for that identity. It does not grant a role. The following example decision files are **SIMULATED**, intended only for the example SYN01 input and fixture mode. Versions are sequential for a fresh store.

```sh
.venv/bin/python -m farajamh review SYN01 --decision examples/reviewer.json --version 1 --token-env FARAJA_DEMO_KE_TOKEN
.venv/bin/python -m farajamh review SYN01 --decision examples/reviewer.json --version 2 --token-env FARAJA_DEMO_TZ_TOKEN
.venv/bin/python -m farajamh adjudicate SYN01 --decision examples/arbitrator.json --version 3 --token-env FARAJA_DEMO_ARBITRATOR_TOKEN
.venv/bin/python -m farajamh review SYN01 --export-package work/review-package --token-env FARAJA_DEMO_ARBITRATOR_TOKEN
```

The first review remains `AWAITING_REVIEW`; quorum moves it to `AWAITING_ARBITRATION`. Approved sign-off produces `ADJUDICATED` and triggers all three lookups. Other arbitrator decisions produce `UNRESOLVED`, `NEEDS_CONTEXT` or `REJECTED`, with no terminology/mapping release.

## Local concepts, mapping and additional evidence

```sh
.venv/bin/python -m farajamh curate SYN01 --decision examples/curation.json --version 4 --token-env FARAJA_DEMO_CURATOR_TOKEN
.venv/bin/python -m farajamh mapping-review SYN01 --decision examples/mapping.json --version 5 --token-env FARAJA_DEMO_CURATOR_TOKEN
.venv/bin/python -m farajamh export-sssom --demonstration --out work/example-export --token-env FARAJA_DEMO_CURATOR_TOKEN
.venv/bin/python -m farajamh add-evidence SYN01 --decision examples/new-evidence.json --version 6 --token-env FARAJA_DEMO_KE_TOKEN
```

`curate` requires an adjudicated meaning ID and records a stable local sense; it never auto-adds every utterance to CKB. Updating an existing sense creates a version and marks dependent records stale. `reuse_approved` is explicit, and applicability stores no person ID or utterance timestamp. Mapping decisions require `resource`, `sense_id`, retrieved candidate ID, directed predicate, evidence and rationale. Valid actions are `approve`, `reject`, `gap`, `unresolved`, `contest`, `challenge_meaning`. Gaps have null candidate/predicate and require a successful scoped search. Contest/challenge reopens adjudication; adjudicate again before new mapping approval. `add-evidence` preserves an external citation/text separately and also reopens meaning. No external URL is automatically fetched from evidence.

The sample new-evidence command marks the earlier demonstration export stale in the application audit. Old snapshots are retained; they must not be presented as current decisions. Review corrections likewise append versions rather than editing earlier submissions.

## Terminology import and real-resource execution

Use the complete RF2/OWL import invocations in [SETUP.md](SETUP.md). Every `import-terminology` action takes an explicit new destination index, resource release and local source files. The importer refuses to overwrite an existing index. SNOMED requires `--concepts`, `--descriptions`, `--language`, `--edition`, `--release`, `--refset`, `--index`. MFOEM/MFOMD require `--owl`, `--release`, `--index`.

Copy `config.yaml` to a real configuration, explicitly change the mode/providers/releases/identity profiles, and use a fresh store. Keep `synthetic: true` on every input. No models or ontologies are automatically downloaded.

```sh
.venv/bin/python -m farajamh --config local-research.yaml preflight
.venv/bin/python -m farajamh --config local-research.yaml batch pilot/utterances.jsonl --manifest pilot/manifest.json
# Actual human reviewers and arbitrator now submit decisions in the UI or via CLI.
.venv/bin/python -m farajamh --config local-research.yaml export-sssom --out work/approved-release --token-env FARAJA_TERMINOLOGY_TOKEN
```

These real-resource commands are illustrative and were not executed: authorized terminology releases, actual models and authorized real reviewers were not supplied. Export without `--demonstration` rejects fixture/simulated artifacts and re-verifies approved targets and resource versions. Unresolved mappings stay in JSON; no invented targets are emitted.

## Reporting and tests

```sh
.venv/bin/python -m farajamh report --out work/current-report
.venv/bin/python -m farajamh scorecard
.venv/bin/python -m pytest -q
```

`scorecard` prints, per model, how its readings compared with reviewer-approved meanings: how often the reviewer started from its reading (and how often that was a minority reading), the reviewer's optional ratings, average self-reported confidence on readings rated correct versus wrong, and run time. `report` also writes it to `model-scorecard.csv`. The same table is on the review screen under **Model scorecard**. Counts cover approved synthetic cases only and are not accuracy.

`report` reads the configured store and writes metrics, full dossiers and the audit log. Use the pilot's already-generated report for its separate database. Real reviewer metrics remain `NOT MEASURED` until actual nonsimulated reviewer submissions exist. The HTTP integration test needs loopback bind permission; it does not call external services.
