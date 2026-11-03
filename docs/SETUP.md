# Setup, models and authorized terminology

> **Scope: earlier prototype / historical evidence.** The [v9.1 infographic](WORKFLOW.md) now defines the process. This document does not prove that process is implemented. See [ALIGNMENT.md](ALIGNMENT.md) for conflicts and missing features. The approach is not yet adopted by FarajaMH and testing is dummy-data only.

## Environment

Use Python 3.11+. This build was executed with Python 3.13.12 on macOS; the system `/usr/bin/python3` here is 3.9.6 and is too old. `requirements.lock` pins the exercised core dependency closure. `validation-requirements.lock` records the optional official-validator environment. The virtual environment already created in this directory is local machine state, not a portable deliverable.

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m farajamh --help
```

`pyproject.toml` pins PyYAML, jsonschema, RDFLib and openpyxl; pytest is the test extra. No services beyond the single Python process/SQLite are required. FTS5 must be present in SQLite for local terminology indexing. Do not store licensed RF2 files or credentials in version control; `.gitignore` excludes `licensed/`, `.env`, runtime stores and virtual environments.

## Execution modes

`fixture` uses the deterministic four-configuration fixture panel, fictional terminology candidates and application/network guards. CLI fixture execution additionally patches socket connection/DNS entry points to fail closed. The local review server must accept loopback browser connections, but the outbound adapter gateway continues to reject all fixture-mode network calls.

`local` permits only loopback model endpoints and local OWL/RF2 indexes. Change all model providers to `ollama`, keep endpoints on `127.0.0.1`, choose actual installed model names and pin actual terminology releases. Fixture providers are forbidden in real modes. All models execute sequentially with `keep_alive: 0`, limiting simultaneously resident weights.

`connected` additionally permits explicitly allowlisted HTTPS origins. MFOEM/MFOMD can use OLS; an OpenAI-compatible model uses `provider: openai_compatible`, its exact endpoint/model, `key_env: FARAJA_API_KEY` and supported settings. Add the origin to `network.allowed_origins`. The adapter appends `/chat/completions`; supply an endpoint including `/v1` where required. Keys come only from environment variables. Redirects and URL-embedded credentials are refused. No paid/remote calls were run during development.

There is no general-purpose policy/ODRL interpreter: the source, permission, endpoint, state and export requirements are directly enforced by application code. Trusted local configuration is an operator boundary, not a multi-tenant identity management system.

## Ollama acquisition and resource expectations

Install Ollama separately from its official distribution. Acquire models only after checking licenses and hardware capacity; development did not download model weights. Illustrative manual acquisition commands are:

```sh
ollama pull qwen2.5:3b
ollama pull llama3.2:3b
ollama pull gemma3:4b
ollama pull qwen2.5:14b
ollama list
```

These names are reference configurations, **not measured performance claims**. Availability and tags may change; the adapter records the actual digest returned by the installed server. A configured missing model fails visibly and is never substituted. Use at least three distinct configurations; the reference pilot has four. Changing only a display ID is rejected as duplicate configuration. Same-family models are not independent scientific raters just because their configuration IDs differ.

Approximate planning arithmetic for 4-bit weights is parameters × 0.5 bytes before quantization metadata, caches and runtime overhead: about 1.5 GB raw for 3B, 2 GB for 4B and 7 GB for 14B. These are lower-bound weight estimates, not measured resident memory. Context/KV caches and backend overhead can add several GB. Plan to benchmark 3–4B models on roughly 8–16 GB machines and a 14B comparison model on roughly 16–32 GB or larger, with substantial variation; CPU execution can be slow. Sequential execution does not guarantee any individual model fits. RF2 indexing additionally requires disk space for source files, staging/index tables and FTS, potentially several times the release's tabular size. Full-release indexing performance was not measured.

Small models may produce invalid JSON, literal renderings, missed Kiswahili nuance or unsupported dialect interpretations. The seed/settings are recorded, but seeds do not guarantee identical outputs across hardware, model digests or backend versions.

## MFOEM and MFOMD

Acquire the relevant official ontology release files outside the project and record their version IRIs and checksums. Supported import formats are RDF/XML OWL and Turtle. The importer indexes explicitly labeled `owl:Class` entities, labels, available definitions, exact/alternative synonyms and obsolescence. It does not follow remote imports or perform OWL reasoning; supply the intended complete ontology content, and report any imports that matter to coverage. The release argument must match `owl:versionIRI` present in the file.

```sh
.venv/bin/python -m farajamh import-terminology MFOEM \
  --owl /authorized/ontologies/mfoem.owl --index work/mfoem-release.sqlite \
  --release 'REPLACE_WITH_DECLARED_VERSION_IRI'
.venv/bin/python -m farajamh import-terminology MFOMD \
  --owl /authorized/ontologies/mfomd.owl --index work/mfomd-release.sqlite \
  --release 'REPLACE_WITH_DECLARED_VERSION_IRI'
```

Set each YAML resource's `index`, `adapter: owl` and exact release. Alternatively use `adapter: ols` with the configured OLS endpoint/ontology name and the actual `config.version` reported by that endpoint. Version absence or change is a blocking prerequisite, not a silent fallback to an unknown release. Search results are followed by ontology-scoped term retrieval. Some ontology IDs use namespaces different from the ontology name; OBO IRIs are converted to their actual CURIE prefix and declared in the export.

No live OLS ontology search or real OWL import was verified in this build. The tests exercise both resources with mocked OLS responses and generated OWL graphs, including wrong releases and failed searches.

## Mandatory SNOMED CT

Obtain an authorized RF2 Snapshot release for the intended edition and use conditions through the relevant distribution/licensing channel. Consult [SNOMED International acquisition guidance](https://www.snomed.org/get-snomed) and your organization's licensing authority. This prototype does not assert whether a particular Kenya/Tanzania use is licensed. Do not redistribute release files, credentials, or unrestricted derivatives on the basis of this demo.

Extract the matching Snapshot concept file, description file and language-reference-set file. Configure the intended language refset explicitly; the default example `900000000000509007` is US English selection, not a claim that it is appropriate for all study uses. Use a new index path per release.

```sh
.venv/bin/python -m farajamh import-terminology SNOMED_CT \
  --concepts /authorized/rf2/sct2_Concept_Snapshot_EXAMPLE.txt \
  --descriptions /authorized/rf2/sct2_Description_Snapshot-en_EXAMPLE.txt \
  --language /authorized/rf2/der2_cRefset_LanguageSnapshot-en_EXAMPLE.txt \
  --edition 'http://snomed.info/sct/REPLACE_WITH_EDITION_ID' \
  --release 20260101 --refset 900000000000509007 \
  --index work/snomed-20260101.sqlite
```

These paths/dates/edition are **illustrative**, not an available release. Set YAML `mode: local` or `connected`, `SNOMED_CT.index`, edition, release and language_refset to the imported metadata. SNOMED stays enabled and uses `adapter: rf2`; OLS is not a substitute. No credential or release file is included. The importer does not validate licensing; authorization is the operator's prerequisite. The [RF2 concept specification](https://docs.snomed.org/snomed-ct-specifications/snomed-ct-release-file-specification/component-release-file-specification/4.2-file-format-specifications/4.2.1-concept-file-specification) defines the source fields used by the importer.

Run `preflight` after configuring releases. Nonzero exit and `UNAVAILABLE` are blocking prerequisites. Search failures and no-results are separately reported. Successful required-resource searches do not require an accepted mapping into every resource.

## Human roles

Replace/add identity profiles for actual research reviewers: distinct reviewer/arbitrator identities, terminology-qualified mapping reviewer and curator roles, declared expertise and locality/variety familiarity. Tokens must be different per identity and stored only in the specified `FARAJA_*` environment variables. These declarations do not certify credentials or infer ethnicity. The study team must constitute and authorize its Kenyan/Tanzanian language, cultural, clinical and lived-experience panel. Example accounts are unmistakably simulated and cannot be used in local/connected mode.

The prototype is not hardened for untrusted users sharing a machine or network. It binds to loopback, validates Host/Origin, escapes display text and checks backend roles/versions. Production identity, encrypted storage, backups, retention, secure deployment and incident management require a separate deployment design.
