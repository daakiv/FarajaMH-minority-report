# Review response and next test plan — 28 October 2026

Source reviewed: `FarajaMH Minority_review.pdf`, particularly the updated E1 findings and next-test/environment recommendations on pages 24–34. These are review recommendations, not evidence that every proposed change is implemented.

## Recommended next case

Use `pilot/kiswa-live-05.json`:

> Kabla ya mkutano na bosi, nasikia moyo inadunda, roho inaenda mbio.

Validated expression: **moyo inadunda, roho inaenda mbio**, character offsets **34–66**, end exclusive. Retain the meeting/boss context. Original wording is preserved; linguistic correction must be recorded, not silently substituted. The proposed PDF's `recurrent` time qualifier is not established by this single sentence; the prepared input uses `unknown`.

Local preflight passed: source schema, exact substring validation, and dictionary lookup returning **DUMMY_DICT_09**, code **Ob**, version **dummy-0.1**, unapproved. This is a test-library match, not a culturally validated interpretation. This was the pre-implementation snapshot. See the dated Now-phase validation below for fresh model tests. No meaning or mapping has been approved during those tests.

### Test procedure and acceptance record

1. Freeze the test code/configuration and use the isolated test database described below. Record input, prompt, model digest and terminology release provenance.
2. Run independent models on the marked expression without dictionary exposure. Count usable outputs; manually check whether each gloss actually describes the idiom. JSON validity alone does not establish translation accuracy. Do not require the models to disagree or manufacture both somatic and emotional readings to pass.
3. Display DUMMY_DICT_09 after the first pass with its matching-rule version, context limits and unapproved status. Evaluate the original spelling and the proposed `unadunda` variant separately with linguistic review.
4. Reviewer assesses plausible bodily and emotional interpretations, category, qualifiers and uncertainty. Assess safety separately. No keyword hit is not safety clearance; emotional context does not establish a physical symptom's cause.
5. Only after meaning approval, approve appropriate search terms (the PDF suggests `heart`, `palpitations`, `fear`, `anxiety`). Do not treat these suggestions as already approved or search all emotional terms for a bodily-only meaning without justification.
6. Record retrieved IDs, source/release, per-query coverage, top-eight relevance and rejected candidates. The PDF's MFOEM:000139, MFOEM:000026, MFOEM:000028 and MFOMD:0000136 / 0000184 are proposed check targets; verify them against the live pinned source before relying on them. SNOMED “Palpitations” is an unverified expectation in the PDF, not a guaranteed hit. Do not hardcode expected IDs into retrieval. Measure absence and irrelevance as test findings.
7. Reviewer saves a local concept and explicitly signs off, defers or rejects a relationship. Do not automatically approve a mapping to satisfy the test. Confirm audit persistence and that experimental SNOMED mappings remain export-blocked. A capped search cannot demonstrate a definitive semantic gap.

## One test environment now

Recommended, **not yet migrated**:

- One interactive server and the existing UI, using `config.live-test.yaml`: synthetic data, local models, public real terminology retrieval, experimental SNOMED, named reviewer. Say **synthetic test / real retrieval**, rather than “LIVE”, which could suggest patient deployment.
- Historical migration is deferred. Under the current task restriction, do not open, copy or modify `work/research.sqlite` or any other existing runtime database. Use fresh temporary pilot databases. Any later archive/backup or migration needs a separate authorized task; never relabel or copy approvals silently.
- Fixture tests and dry-runs remain available in isolated temporary databases. They must not open the interactive test database.
- Add and test a mutation guard against dossier/runtime mode mismatch before starting KISWA-LIVE-05. Ideally also pin database environment identity, since file sharing is the underlying hazard. Read-only archive access should remain possible.
- Put the source under version control with an ignore policy for tokens, runtime databases, logs and restricted terminology files. Inspect the staged content before the initial commit; record commit plus dirty-state/content hash in run provenance. No repository publication is implied.
- Test the backup/restore and one-server launch procedure. Keep secrets in environment variables.

These changes are preparation gates, not completed deployment work. The current running app still uses the historical database; this task has not moved or deleted records.

## Before patient-data use

Use a separate deployment, database and credentials; never turn the synthetic test database into a patient database.

- Project adoption, ethics/data-sharing arrangements, approved model hosting, access controls, retention and incident procedures must be agreed by the project.
- Preserve the current synthetic-only gate until a deliberate, reviewed implementation change. Do not label real data synthetic to bypass it.
- Use expression spans consistently, with review responsibility and exact-span checks. Resolve parent-versus-expression approval/export scope to prevent duplicate or conflicting mappings.
- Evaluate translation and expression grounding on the workshop test pack; document failure rates and language limitations. “Two usable models” is a pilot criterion, not clinical validation.
- Version the curator-approved dictionary and linguist-reviewed matching rules; do not call dummy-0.1 a validated v1.0.
- Review the risk lexicon and escalation protocol with the appropriate clinical/community team. Inherit unresolved parent safety concerns in child reviews and record their resolution separately.
- Assign qualified reviewers and an explicit second-opinion process.
- Verify terminology source access and export permissions. Replace experimental SNOMED with an appropriately authorized source before relevant release exports. Evaluate ranking against independent reviewer relevance labels; similarity is not mapping confidence.
- Validate release artifacts against supported standards. Keep gaps and rejections distinct from positive mappings. Do not invent confidence values, persistent prefixes or OMOP mapping rules just to populate an export.

## Review corrections and outstanding priorities

The report contains successive snapshots: early claims about absent spans, dictionary loading, shared categories and ranking have been superseded by the later implementation. The later E1 findings remain important. The next engineering priorities are structured model output and concise validation feedback; expression-grounded readings; inherited safety context; preventing mode contamination; and independent ranking evaluation. Matching-rule coverage is still deliberately narrow. The nominal live ranking improvement does not establish correctness.

The report's “safe to run” claim based on keyword absence is too strong. Its span 34–66 is correct. Requiring particular model disagreement, target codes or a completed approval should be replaced by observed test results and reviewer decisions. SSSOM confidence and gap representation require a defined policy; they should not be fabricated.

## HITL validation delivered in this change

Missing or invalid inputs are highlighted in red, with inline field messages, a linked error summary, focus on the first affected field and accessible invalid-field attributes. Covers meaning count/details, supporting evidence, applicability confirmation, safety note, local concepts, mapping prerequisites, additional evidence and expression inputs. Optional DAP and dictionary reuse are not required. Existing entries remain in place after validation failure. Backend errors preserve their messages and target the field when a schema path is available. The status bar no longer overlays scrolled content.


## Now-phase implementation — 28 October 2026

**Verified (code and automated tests):**

- A1–A4: `intake.prepare_case` validates the simple form before model calls. Original text is preserved, repeated exact expressions require an occurrence, offsets use Unicode code points, and optional context becomes E2. Reviewer role, synthetic boolean confirmation, ID uniqueness and identifier scanning are required. The entering reviewer is audited. The future simple batch/staging routes must call this function; the existing full-source CLI still has its schema and semantic checks.
- B1–B2: a single background worker runs models sequentially, then dictionary, comparison and saving. Each worker owns its database connection. Authenticated polling exposes status events only; queue requests remain responsive. IDs remain reserved for the server lifetime, including failed runs (use a new ID to retry).
- B3–B5: the screen shows eight record-derived status chips, model failure reasons and timings, and installed/missing/unavailable checks for interpretation and embedding models. Missing models get a pull command; nothing is pulled or substituted. No percentages or time estimates.
- C1–C3: escaped HTML ID patterns, exact-expression highlight, occurrence chooser, suggested available IDs, unknown default time, red field errors, and per-source terminology summaries.
- D1–D3: Ollama receives the complete output schema in `format`; full validation remains. Model set, prompts and minimum votes are unchanged. Per-run digest, duration, result and failure reason are retained. A schema-valid reading is not a validated interpretation.
- E1–E3: ranking says embedding, lexical order or not recorded. Export readiness uses shared recorded-state blockers with the exporter; a clear result means **ready for final checks**, not guaranteed export. Export still verifies current releases and targets across eligible cases. Mutations check case mode and all recorded database modes before proceeding. Read-only viewing remains possible; existing databases were not migrated or opened during this work. No metadata pin is added to an empty database; its first recorded mode establishes the guard.

**Scope still deferred:** B6 durable restart recovery; G1 simple CSV/JSONL batch intake; G2 staging view, deduplication and outbox; environment migration and production launch. Restarted polling reports unavailable/interrupted status and asks the user to check the queue. It does not automatically rerun models. LOINC/OMOP lookup and patient-data deployment remain unimplemented.

### F1–F3: decisions still needed; not implemented

- F1 proposed next-version English function words: `a an the and or my your his her our their i me we you it is am are was were be been being of to in on at with for`. Retain negation. The prior in-memory comparison found 05→DUMMY_DICT_09 unchanged, 06→DUMMY_DICT_15 before and no candidate after, 07→DUMMY_DICT_09 unchanged. This is a proposal for linguistic review, not a released matching rule. `phrase-features-2` remains in use.
- F2 reduce output failures first, then measure. Adding a fourth model provides tolerance of one failure but adds a sequential model call; lowering the minimum changes the participation rule and needs approval. Neither is changed here.
- F3 retain the current all-source success requirement. A future explicitly labelled partial export could retain useful MFOEM/MFOMD mappings when SNOMED is unavailable, but requires agreed provenance, completeness and licensing rules. Experimental SNOMED targets remain export-blocked.

### Pilot evidence and limits

Test and browser results are recorded below after completion. Only supplied invented examples and fresh temporary databases are used. No meaning approval, safety clearance, DAP association or terminology mapping is manufactured to complete the pilot. Consequently terminology remains not searched until a human approves meaning/search terms, and export is blocked. This validates the gate, not live terminology retrieval quality.

### Verified before/after local-model measurement

Same supplied synthetic input per pair; original prompts and models retained. One observation per configuration, not a failure-rate estimate.

| Case | Format | Gemma | Qwen | Llama | Usable |
|---|---|---|---|---|---|
| E1 | before | FAILED / 73.36 s | COMPLETED / 21.62 s | FAILED / 21.86 s | 1/3 |
| E1 | after | COMPLETED / 31.31 s | COMPLETED / 11.33 s | COMPLETED / 10.8 s | 3/3 |
| KISWA-LIVE-05 | before | FAILED / 47.88 s | COMPLETED / 22.09 s | FAILED / 22.32 s | 1/3 |
| KISWA-LIVE-05 | after | FAILED / 52.91 s | COMPLETED / 10.84 s | COMPLETED / 10.75 s | 2/3 |

Gemma still failed the post-change 05 run on unauthorized evidence references. Full validation rejected that output. Structured output improved format reliability in these observations; it did not establish semantic correctness or solve evidence grounding. No schema simplification, prompt change or model substitution was made. Digests and reasons: `NOW_MODEL_MEASUREMENTS.json`.

### Verified browser test pack and final checks

All three cases were submitted through the new intake screen on isolated port 8876, with a fresh temporary database. Existing runtime databases were not opened, copied, migrated or changed. Browser evidence: `pilot-evidence/intake-form.png`, `intake-validation.png`, `run-panel.png`, `status-strip.png`. Digests, failure reasons and export blockers: `NOW_BROWSER_PILOT.json`.

| Case | Span | Gemma | Qwen | Llama | Dictionary | Comparison |
|---|---|---|---|---|---|---|
| KISWA-LIVE-05 | 34–66 | FAILED / 52.71 s | COMPLETED / 11.21 s | COMPLETED / 10.44 s | DUMMY_DICT_09 | INSUFFICIENT_PARTICIPATION |
| KISWA-LIVE-06 | 33–65 | COMPLETED / 31.61 s | COMPLETED / 10.73 s | COMPLETED / 9.21 s | DUMMY_DICT_15 | TIED |
| KISWA-LIVE-07 | 34–67 | COMPLETED / 25.44 s | COMPLETED / 11.44 s | COMPLETED / 10.31 s | DUMMY_DICT_09 | TIED |

**Verified:** Each case has MFOEM, MFOMD and SNOMED `NOT_SEARCHED`; ranking was not run. Each is export-blocked pending approved meaning and successful required-source searches. This is expected: the pilot does not approve decisions for the reviewer. English retained the known false dictionary candidate DUMMY_DICT_15. An in-memory rerun of the proposed F1 English function-word list confirmed the before/after table; see `NOW_DICTIONARY_PROPOSAL.json`. No dictionary rule was changed.

**Verified:** Final full suite: **105 passed, 0 failed**, with 12 third-party deprecation warnings. Initial sandbox execution blocked the HTTP bind (85 passed, 1 environmental failure); rerunning with approved loopback access passed. A later indentation error introduced during editing was caught and fixed before the final full pass. Node syntax checking passed. Chromium's `v`-flag pattern accepted `FARAJA:moyo-inadunda` and rejected `FARAJA:bad id`. Browser checks confirmed red synthetic-confirmation errors clear after correction, the 34–66 highlight, model availability, active-run queue responsiveness and eight saved-record chips. Automated tests cover intake refusals, non-ASCII/repeated spans, English/code-switched input, duplicate reservations, worker connection ownership, actor audit, structured-output payload/failure metrics, mode guards and shared export blockers.

**Unverified / not claimed:** linguistic correctness, clinical validity, ranking relevance, terminology results for these unapproved meanings, production safety, persistent job recovery, migration/backup of historical data and adoption by FarajaMH. Before/after model observations use one synthetic run per condition; timing depends on local runtime/cache, and is not a benchmark or guarantee. The existing server remains untouched.

### Verified user-authorized meaning review and retrieval — 29 October 2026

The user chose to retain both meanings for KISWA-LIVE-05: racing-heart sensation (S, somatic) and feeling anxious before the meeting (E, emotional). Version 2 recorded that choice, evidence E1 and applicability confirmation; safety stayed uncertain and DAP associations stayed empty. Searches used palpitations, racing heart, anxiety and nervousness. The first MFOMD lookup failed with RemoteDisconnected; a single rerun succeeded and produced version 3.

Verified final results: MFOEM 6 candidates (release 2025-07-31), MFOMD 16 (2020-04-26), SNOMED CT 46 (pinned release 20251017). All three used local embedding ranking. Examples: MFOEM:000124 feeling nervous; MFOMD:0000184 nervousness; SNOMEDCT:80313002 Palpitations and SNOMEDCT:48694002 Anxiety. These are retrieved candidates, not approved mappings or diagnoses. No local concept, dictionary reuse or mapping approval was submitted.

Implementation limitation verified by code inspection: queries run individually, but candidates are pooled by source and ranked against both accepted meanings together. This is not yet a separate ranking/list per meaning. Disorder-level candidates must not be treated as established by the synthetic utterance. SNOMED remains experimental for lookup; approved experimental targets cannot be exported.

Evidence: `KISWA_05_TERMINOLOGY_FIRST_LOOKUP.json`, `KISWA_05_TERMINOLOGY_RESULTS.json`, and `pilot-evidence/three-source-terminology.png`. Only the isolated temporary pilot database was used.


## Review findings corrected — 29 October 2026

### Verified code defects and fixes

1. **Cultural-note validator:** `CN1` is a note ID; `E1` is its evidence reference. Validation now checks `reference`. Genuine schema failures and evidence/consistency failures have distinct messages, including which note reference needs correcting. The original model prompt, configured models and participation threshold are retained. Retry feedback names the applicable validation categories.

   **Correction to earlier findings:** previous statements blaming Gemma for the `CN1 → E1` rejection were wrong. That was an application validator defect. The old measurements record the observed failure under the old code; they must not be read as evidence of poor model output quality. Historical saved records were not changed. The three historical saved replies were not opened or replayed because of the runtime-database restriction.

2. **Per-meaning retrieval:** every meaning has its own query set, source results, coverage and ranking context in `by_meaning`. Source-level data retains a compatibility index for historical mapping references, not a pooled ranking. Failure in one meaning remains visible and blocks aggregate source readiness. The mapping backend checks candidates against the local concept's meaning; candidates belonging only to another meaning cannot be approved against it. Historical pooled screens are labelled until explicitly refreshed.

3. **Experimental export exclusions:** approved lookup-only experimental targets are omitted from SSSOM and written to `excluded-mappings.json`, returned in the export result and recorded in the audit event. Eligible mappings from other sources can export. This changes only the experimental-target handling requested in the latest review. The all-required-sources search-success policy remains: unavailable or failed sources still block the export. Stale, inactive or otherwise ineligible non-experimental targets retain their guards. Exclusions do not change stored mapping decisions.

4. **Status strip:** review and terminology start neutral; amber marks an actual attention state. Initial case storage leaves Record neutral, with “Case saved; decision pending”. A recorded human decision advances Record. These statuses remain based on saved dossier data.

5. **Recurrent time:** available at intake and meaning editing, supported by local-concept applicability validation. It is chosen by the reviewer, not inferred automatically from this particular 05 example.

6. **Candidate selection:** results show meaning, source and rank; definitions expand before a Select button is shown. Selecting prepares a form or requests the corresponding local concept; it does not approve a mapping. Changing source/concept/candidate resets the approval choice and predicate. Inactive candidates remain disabled. Nothing is silently removed as noise.

### Verified checks

The regression suite passed **112 tests, 0 failures**, with 14 dependency deprecation warnings. Tests cover valid CN1→E1 and invalid reference rejection, failure-category wording, separate query/ranking contexts, no cross-meaning approvals, visible per-meaning failures, neutral initial statuses, recurrent applicability and mixed exports with explicit experimental exclusions. Node JavaScript syntax checking passed. All databases used for these tests were fresh temporary databases.

Fresh live 05 run: Gemma COMPLETED in 26.03 s, Qwen COMPLETED in 10.47 s, Llama COMPLETED in 10.32 s; **3 usable readings**, comparison **TIED**. Gemma's accepted reply contains note `CN1` citing `E1`. This verifies the application fix on a fresh run; it does not validate translation accuracy. Details: `REVIEW_FIX_MODEL_CHECK.json`.

### Coverage probes — verified observations, not approved expansions

Read-only probes against the pinned public sources found:

- MFOEM “heart beating at faster rate” and “heart beating faster” each retrieve **MFOEM:000139**. The earlier 05 terms “palpitations” and “racing heart” did not retrieve this concept. This is query coverage, not absence of an MFOEM concept.
- SNOMED “chest heaviness” returns NO_RESULTS; “tight chest” retrieves **SNOMEDCT:23924001**, Tight chest. These expressions are not silently treated as equivalent. The reviewer must consider whether an alternate query and any resulting relationship fit the approved meaning.

Probe file: `REVIEW_FIX_COVERAGE_PROBES.json`. No approved search terms, matching rules or database records were altered by the probes. SNOMED remains an explicitly experimental public lookup source.

### Remaining unverified / open

Translation accuracy, unsupported additions such as “news”, safety-flag calibration, workshop linguistic validity and clinical relevance need reviewer-labelled evaluation. The application retains uncertain model flags for review and displays their origin; it does not automatically clear them as false positives. Per-meaning ranking improves visibility but does not establish that the top result is a suitable mapping. Disorder-level or questionnaire-score hits remain candidates requiring rejection or justified relationship review.

The updated verification server uses a newly created temporary database on **8877**. The earlier **8876** process and its user-entered cases, and all historical runtime databases, were left untouched. Do not treat refreshing the old process's page as upgrading its Python backend.


### Verified browser and additional live checks for these fixes

The refreshed 05 test replayed the user's earlier choice to retain both meanings, with safety uncertain and DAP unassigned. No local concept or mapping was approved. Separate results were:

| Meaning | MFOEM | MFOMD | SNOMED CT |
|---|---:|---:|---:|
| Racing-heart sensation before meeting | 0 | 0 | 6 |
| Feeling anxious before meeting | 6 | 16 | 40 |

Palpitations (SNOMEDCT:80313002) ranked **1 within the bodily meaning**, and Anxiety (SNOMEDCT:48694002) ranked 1 within the emotional meaning. The zero-result panels remain visible; they do not borrow another meaning's hits. Expanding Palpitations revealed its definition and selection action. Selecting it without a corresponding local concept requested local curation and left mapping action unresolved, predicate empty and saved mapping count zero.

The status strip was checked in Chromium before review: steps 6, 7 and 8 had neutral classes, with Record labelled “Case saved; decision pending”. Recurrent time options were added to intake and reviewer editing. Screenshots: `pilot-evidence/fixed-neutral-statuses.png`, `separate-meaning-body-results.png`, `separate-meaning-emotion-results.png`. Per-meaning results: `REVIEW_FIX_SEPARATE_LOOKUPS.json`.

A fresh KISWA-LIVE-01 run used the exact synthetic text supplied in the pasted screen: Gemma COMPLETED (39.32 s), Qwen COMPLETED (10.33 s), Llama COMPLETED (14.58 s), 3 usable votes and comparison TIED. Gemma notes CN1 and CN2 cite E1 and pass. The queue is PRIORITY because Gemma suggests uncertain risk in this run. Qwen again introduces “because of the news”, absent from the supplied source. Thus output validation success does not establish translation fidelity or safety-assessment validity. Details: `REVIEW_FIX_KISWA_01.json`. This new case remains awaiting human review; it was not automatically approved.

The updated test page is http://127.0.0.1:8877/ with the pilot-only token `isolated-pilot-token`. `tools/verify_review_fixes.py` always creates a fresh temporary database; it does not reopen earlier runtime files. The original page on 8876 retains the user's existing cases and its earlier Python backend. Use 8877 to inspect these fixes.
