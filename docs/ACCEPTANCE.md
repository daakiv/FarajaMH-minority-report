# Acceptance evidence and remaining prerequisites

> **Scope: earlier prototype / historical evidence.** The [v9.1 infographic](WORKFLOW.md) now defines the process. This document does not prove that process is implemented. See [ALIGNMENT.md](ALIGNMENT.md) for conflicts and missing features. The approach is not yet adopted by FarajaMH and testing is dummy-data only.

Build date: 5 October 2026 (Africa/Nairobi). This document distinguishes implemented software, tested fixtures and unverified real resources. No automatically generated or simulated approval is a real human-reviewed research result.

## Executed evidence

| Action actually executed | Result |
|---|---|
| Read the pasted revised prompt, earlier `DESIGN.md`/README/workflow documentation, inspect both available local images | Revised requirements implemented; exact original WP2/“When Translation Models Split…” image files not located. |
| `git -C ../the-minority-report rev-parse HEAD` | `a7cb9cbf90cffb186c69699b5a188f970d22e5b9`. Relevant upstream functions inspected; defects verified in `ARCHITECTURE.md`. |
| Create new top-level `farajamh-cultural-interpretation-pipeline/` | No files modified in upstream or the earlier adaptation. Earlier adaptation had pre-existing modifications; those were preserved. |
| Create Python 3.13.12 venv and install pinned dependencies | Successful. Initial package download was sandbox-blocked, then completed with approved network access. No model weights or ontology releases downloaded. |
| `python tools/build_schemas.py`; `python tools/build_pilot.py` | Checked-in schemas and twenty deterministic synthetic inputs/responses generated. |
| `python -m pip install --no-deps --no-build-isolation -e .` | Installed runnable `farajamh` console entry point from local source. |
| `python -m farajamh dry-run --out evidence/pilot-final` | Twenty inputs processed with network blocked. All simulated review/arbitration/curation/export decisions persisted. Current source code hash recorded in each dossier. |
| `python tools/validate_upstream.py evidence/pilot-final/SIMULATED-artifacts` | Official SSSOM schema model 1.0.0 accepted 3 demonstration rows. mlcroissant 1.0.22 loaded/read 18 adjudicated synthetic rows and 3 mapping rows. Network blocked. Result: `evidence/upstream-validation-final.json`. |
| `python -m pytest -q --junitxml=evidence/tests-final.xml` | **56 passed** with official validators installed. Initial local HTTP binding failed inside the sandbox; approved loopback rerun passed. Final JUnit XML is delivered. Third-party RDFLib/LinkML deprecation warnings remain. |
| `python -m farajamh init`; `batch ... --manifest ...`; `preflight`; `report`; `compileall` | Persistent twenty-item awaiting-review queue created; fixture preflight/report and Python compilation succeeded. Normal batch created no approvals. |
| Start `review --serve --port 8765`, open in-app browser, authenticate simulated reviewer, select SYN01 | Queue, actual dossier and tied-vote counts visibly loaded. Narrow-window queue is scrollable. Screenshot: `evidence/review-ui.jpg`. HTTP test separately confirms decision persistence, authentication, and Origin checks. |

Development snapshots in `evidence/pilot-01` and `evidence/pilot-validation*` are retained, not represented as the final acceptance run. The first Croissant check exposed missing context terms and local-file URI incompatibility in the reference reader; final output uses the pinned standard inline context and relative file references, and passes actual record iteration.

## Implemented coverage

The offline prototype runs end to end with real voting, permissions, storage, approval and export logic. The persistent UI and CLI support independent reviewers, minority/alternative/multiple readings, unresolved decisions, a distinct human arbitrator, terminology fit review, local concepts, CKB triage and separate contextual assertions. Fixtures mock model and external resource responses, not approval or release policy.

Both MFOEM and MFOMD have executable OLS and local OWL adapters. SNOMED CT has an executable RF2 Snapshot importer, FTS search and identifier verification including concepts/descriptions/language refsets, preferred terms, FSNs, string SCTIDs, module/activity/edition/release. These are implementations, not adapter stubs. Tests use generated tiny OWL/RF2 data and mocked OLS responses; real-resource verification is a separate prerequisite.

Tests cover schema guards; 2–2, 3–1, 2–1–1 and insufficient votes; failed/invalid JSON and retry; abstention; secondary votes; qualifier conflicts; wording differences; risk and uncertainty priority; untrusted approval/evidence fields; same independent prompt/input; offline networking; missing models; hidden independent reviews; role separation; arbitration quorum; minority choice; stale-write rollback; unresolved and simulated release blocking; CKB context mismatch and no copied person/time facts; semantic gap versus failure; invented/inactive targets; mandatory SNOMED absence; external evidence reopening; append-only source/audit; stale export events; RF2/OWL/OLS logic; SSSOM/Croissant validators; review CSV/XLSX; full offline pilot; and authenticated HTTP persistence.

## Assumptions

- **[ASSUMPTION A1]** The infographic's African arbitrator is a designated human identity distinct from reviewers and models. Impact: every new interpretation, and conservatively CKB reuse, needs human arbitrator sign-off.
- **[ASSUMPTION A2]** The revised prompt's transcribed pathway supersedes conflicting earlier local figures and design notes. Impact: arbitration is restored, terminology lookup follows meaning adjudication, SNOMED is required, and gaps are separate JSON rather than invented target rows.
- **[ASSUMPTION A3]** A reviewed semantic-frame grouping proposal is an acceptable inspectable prototype baseline. Impact: paraphrases may fragment, and nuanced contradictions/model frame errors can escape automation; humans inspect original readings and must not equate majority with truth.
- **[ASSUMPTION A4]** Local trusted operators manage YAML identities/roles, environment tokens and authorized terminology acquisition. Impact: configured expertise is not credential verification, and local file administrators can alter the database/application. This is not a hostile multi-tenant service.
- **[ASSUMPTION A5]** All supplied pilot expressions, English glosses, code-switch spans and decisions are constructed software fixtures. Impact: they establish no Sheng/dialect authenticity or cultural/clinical interpretation rule.
- **[ASSUMPTION A6]** A stable local example namespace (`https://example.org/farajamh/`) is sufficient for a local research demonstration. Impact: real publication requires project-owned persistent identifiers and governance; example URIs are not claimed as a deployed registry.
- **[ASSUMPTION A7]** Conservative exact contextual applicability is preferable for initial CKB reuse. Impact: many plausible paraphrases/context variants remain near-matches and invoke models/review. Person references and utterance timestamps never enter reusable applicability constraints.
- **[ASSUMPTION A8]** The four fixed fixture configurations may be treated as a fixed categorical panel to test Fleiss' kappa arithmetic. Impact: no statistical independence or real model performance is inferred.

## Blockers and verification limits

- **[BLOCKER B1 — resource verification]** No authorized SNOMED RF2 edition/release was supplied or imported. Impact: real SCTID/edition/terminology verification remains untested; local/connected configurations without it visibly fail prerequisites and cannot claim complete terminology review or release. The adapter itself and fabricated Snapshot ingestion/search were tested.
- **[BLOCKER B2 — resource verification]** No actual MFOEM/MFOMD OWL release was supplied and no live OLS ontology search was executed. Impact: endpoint/release compatibility and real candidate coverage are unverified; both adapters were exercised using generated/mocked inputs.
- **[BLOCKER B3 — model verification]** No real Ollama ensemble or API inference was run. Impact: hardware fit, latency, valid JSON rate, Kiswahili competence and actual disagreement are unmeasured. Missing-model behavior and HTTP adapter paths are tested against mocked responses. No automatic model acquisition occurs.
- **[BLOCKER B4 — research review]** No authorized real Kenyan/Tanzanian reviewer panel or arbitrator participated. Impact: real reviewer metrics are `NOT MEASURED`; all demonstrated approvals are simulated and excluded from research releases.
- **[BLOCKER B5 — exact figure evidence]** The two exact original figures named in the revised request were not available in the attachment/relevant project files. Impact: alignment with those exact visuals cannot be independently verified; the explicit user-supplied pathway is implemented, and the two earlier local figures were inspected and their differences documented.

## Known limitations and defects

The interface uses structured editable JSON decision forms with readable source/model panels, rather than a finished study-review product. It is persistent and permission checked, but usability/accessibility has not been evaluated by the study panel. There is no identity provider, password recovery, encrypted database, deployment hardening or automatic backup. Authentication errors currently return HTTP 400 rather than a specialized 401/403 status; authorization is still enforced. The UI's terminology tables expose all retrieval details but do not claim calibrated fit scoring.

Grouping is conservative English semantic-frame comparison with explicit qualifier/negation safeguards, not a validated multilingual semantic equivalence model. The schema prevents model-supplied approval fields and ontology search IDs, but cannot prove a rationale is true or that a textual instruction was ignored. Exact contextual CKB matching can have low recall. Cultural notes and all inferred language spans require human review. The risk lexicon misses paraphrases and can flag negated quotations; flags are reviewable and never diagnoses. A synthetic label plus identifier patterns is not a de-identification guarantee.

OWL support indexes explicit classes without remote imports/reasoning. OLS requires an available exact reported release; some services may omit/change version metadata, deliberately blocking the run. RF2 full-release memory/disk/runtime scaling and national-edition complexities were not benchmarked. Imports index a supplied Snapshot rather than merging release dependencies or inferring ontology closure. The core SSSOM validator is an intentionally constrained 1.0 export profile, supplemented by actual validation using the pinned official schema model. The generated Croissant catalog and its referenced CSVs were parsed/read by the pinned upstream implementation; metadata validates file structure, not clinical evidence.

There is no core adapter stub hidden behind the fixture pilot. Remaining gaps are real-resource/model/panel verification, original figure availability, and the stated research-prototype limitations. Before any real-data deployment, obtain study/data governance approvals and a separate threat/privacy assessment, constitute the review panel, validate languages/risk handling, confirm licensing and actual release coverage, benchmark chosen models, and design secure storage/access/retention/operational controls. No configuration switch in this application authorizes real patient data.

## References used for implementation checks

- [SSSOM 1.0 model](https://mapping-commons.github.io/sssom/1.0/spec-model/) and its [Mapping fields](https://mapping-commons.github.io/sssom/1.0/Mapping/) — required slots, CURIE declarations and directed predicates.
- [SNOMED RF2 concept specification](https://docs.snomed.org/snomed-ct-specifications/snomed-ct-release-file-specification/component-release-file-specification/4.2-file-format-specifications/4.2.1-concept-file-specification) and [authorized acquisition](https://www.snomed.org/get-snomed) — source release structure and acquisition prerequisites.
- [Ollama chat API](https://docs.ollama.com/api/chat) and [OLS API](https://www.ebi.ac.uk/ols4/swagger-ui/index.html) — adapter contracts; deployment verification remains separate.
- [Croissant specification](https://docs.mlcommons.org/croissant/docs/croissant-spec.html) — catalog/data references; the pinned `mlcroissant==1.0.22` standard inline context is included in `schemas/croissant-context-1.0.json`.
