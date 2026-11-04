# v9.1 alignment: requirements versus current code

Audit date: 10 October 2026. The [infographic](figures/Minority_Report_FarajaMH_workflow_v9_1.png) is authoritative. This is a partial implementation, tested on dummy data only, not an adopted FarajaMH workflow.

| Step | Evidence in current source | Remaining gap or conflict |
|---|---|---|
| 1 · Source | `schemas/source.json`, `pipeline.App.run`: original text, context and synthetic-input validation | Keep these boundaries. No claim of validated cultural or clinical data. |
| 2 · Expressions | Source has language spans; `App.run` stores an utterance-level dossier | Language spans are not an expression-occurrence review loop. Expression extraction and reviewer boundary corrections are not implemented. |
| 3 · Models | `models.interpret` now receives only source/configuration. `App.run` calls models before local-sense lookup, including known matches. Independent calls, prompt hashes, model metadata and raw attempts exist. | Provider/version pinning must be verified per actual deployment. Fixture identities are not evidence that real models ran. No fixed model count is required by the image. |
| 4 · Dictionary | Existing local-sense retrieval preserves versioned sense references | No approved workshop seed or complete versioned idiom-library import/publication process. Local senses are not a substitute for claiming that process complete. |
| 5 · Compare / route | `agreement.py` compares model hypotheses; `App.priority` preserves risk evidence | Agreed-case sampling is implemented (`App.routing`, off unless `review.agreed_sample_rate` is set). No model–dictionary comparison. Existing majority labels are not approval. |
| 6 · Review | `App.complete_review` supports one configured reviewer through guided fields, with category/DAP annotations, applicability, separate safety and optional second opinion. The same configured identity can curate and sign off terminology. | Legacy CLI commands retain their older quorum. Second opinions require another reviewer; requests are recorded, not automatically assigned or notified. |
| 7 · Terminology | Accepted meanings' search terms drive MFOEM/MFOMD/SNOMED candidates; human mapping decisions exist | No LOINC or OMOP vocabulary adapter. Current required-resource export gates are legacy policy, not prescribed by the infographic. |
| 8 · Outputs | Versioned dossiers, local concepts and SSSOM artifacts exist; simulated artifacts are labelled | No OMOP vocabulary mapping or OMOP export. Existing CSV/XLSX/JSON/Croissant mechanisms are legacy tools, not extra required stages. |
| Feedback | Explicit local-sense curation and versioning exist | No complete new-entry/correction proposal queue with curator-approved dictionary publication. |

## Changes made in this alignment pass

- Saved the exact attached infographic, with its SHA-256 in `WORKFLOW.md`.
- Replaced the README's process claim with the eight-step target and explicit current limitations.
- Superseded the earlier architecture as a workflow authority while retaining its engineering history.
- Removed known-library-match bypass and dictionary entries from model prompts, including retries. Dictionary lookup now follows first-pass interpretation.
- Added regression coverage for prompt isolation, call ordering and generation on known matches.

Historical pilot outputs and acceptance reports are preserved. They describe earlier code, not verification of v9.1. No database migration, live model execution, dictionary import or real-data use is claimed by this pass.

## Decisions not specified by the infographic

These require user clarification, not inferred behaviour:

- Sampling protocol for agreed cases. The user proposed a 10% test rate on 10 October 2026; it is not a validated research sample size. Implemented for testing in `config.live-test.yaml`: a case is agreed only when all usable models are in one group, there is no safety signal, and who, negation and time are recorded. The draw is `sha256(seed|utterance_id)`, recorded with each case, so the sample can be rechecked.
- Approved dictionary version and curator. Room C Free listing and Info plus the definition slide are now supplied as draft sources. Workbook Cs/Ob codes are retained by user instruction; Ob primary category remains blank.
- Who supplies the optional second opinion and how it is assigned. The user authorized one trained reviewer handling meaning, terminology and curation; local reuse approval is explicit. Complete dictionary publication remains unimplemented.
- How expression spans are initially identified and how corrected boundaries affect existing decisions.
- How to identify disagreement with dictionary meanings and applicability limits.
- Which terminology releases/endpoints are available, and how missing sources affect sign-off.
- What makes an OMOP mapping suitable and validated, which optional export is required, and how local IDs are allocated.

The user has answered the initial rate/source/reviewer questions in part. Unresolved permissions and protocol details remain explicit. None is silently filled in from the older prototype.

## Verification for this pass

On 10 October 2026, `.venv/bin/python -m pytest -q` produced 56 passes and one environment failure: the sandbox prohibited the HTTP test from binding localhost. The isolated HTTP test then passed with authorized execution outside the sandbox. Together these runs cover all 57 tests, including the new dictionary-isolation regression. The focused interpretation/governance run passed 41 tests. Existing third-party deprecation warnings remain. These are software tests with synthetic fixtures, not validation of models, cultural meanings, terminology releases or the full revised workflow.

## Workshop dummy material added

`pilot/workshop-dummy/` preserves 48 original listing rows and 10 Info definitions, with file hashes. It supplies 16 invented contextual scenarios, 14 explicitly unapproved dummy dictionary entries, 64 scripted model responses and schema-valid synthetic inputs. Ten scenarios reuse workshop wording; six use invented English wording. No invented context is attributed to workshop participants. Codes Cs/Ob are preserved and R remains separate. Three dedicated tests validate the pack and exercise the current model stage. Dictionary matching, 10% routing and curator publication are still not implemented by this fixture addition.

## Guided single-reviewer screen (11 October 2026)

The user authorized one trained reviewer to handle the review workflow. `review.workflow: single_reviewer` enables an atomic meaning-decision endpoint with version checks, append-only audit and dependent-mapping invalidation. The `demo_ke` fixture account has reviewer, curator and terminology roles. No independent peers or arbitrator approvals are fabricated. Optional second-opinion requests block self-approval until a different reviewer responds, including after new evidence. Dictionary reuse requires explicit curation approval; prior sense versions remain. DAP is an association annotation, not a diagnosis. JSON records are read-only in the new UI.

Verification: 71 tests passed in the sandbox; the sole localhost-binding test passed separately with authorized network execution, covering all 72 tests. Twelve new guided-review tests cover same-person meaning/curation/mapping, explicit dictionary reuse, DAP preservation, invalidation, lookup order, second-opinion independence, invalid submissions, stale versions and multiple meanings. Browser verification used the labelled synthetic `UI-CHECK-20261011` case: meaning approval, local concept and MFOEM relationship saved as versions 2–4 through the same account. Existing source revisions were checked unchanged against a pre-restart SQLite backup. This is software verification, not cultural or clinical validation.
