# Synthetic pilot and metric definitions

> **Scope: earlier prototype / historical evidence.** The [v9.1 infographic](WORKFLOW.md) now defines the process. This document does not prove that process is implemented. See [ALIGNMENT.md](ALIGNMENT.md) for conflicts and missing features. The approach is not yet adopted by FarajaMH and testing is dummy-data only.

The twenty utterances in `pilot/utterances.jsonl` are constructed test examples. Kiswahili glosses, language-span hypotheses, code-switching and all interpretations are unvalidated. No invented Sheng expression is claimed to represent community usage. The four displayed model configurations name reference deployment choices, but every pilot model output is deterministic fixture data, not an actual run of those models.

The manifest enforces `synthetic: true`. Each utterance includes a synthetic speaker reference, source text, context, evidence and assertion/attribution/experiencer/time/setting qualifiers. Region/variety is explicitly null. Code-switching spans are labelled hypotheses. Original text and evidence persist unchanged.

| Items | Software scenario |
|---|---|
| SYN01 | “My heart is burning”: 2 emotional-pain readings and 2 physical-burning readings. Simulated arbitrator preserves both. Neither reading is a verified cultural fact. |
| SYN02 | 3–1 split; simulated reviewer selects minority somatic reading and simulated arbitrator adopts it. |
| SYN03 | 2–1–1 no-majority; unresolved adjudication blocks terminology/export. |
| SYN04–06 | Worry, explicit negation and attributed experience; opposing experiencers stay distinct. |
| SYN07–09 | Three synthetic urgent/uncertain-risk routing scenarios; one-model concern, uncertainty and explicit source wording. No action beyond research priority. |
| SYN10–11, SYN20 | Three non-distress controls: celebration, enjoying food and happy planning. |
| SYN12–14 | Work fatigue, uncertain self-description and an ambiguous spiritual expression. |
| SYN15 | One missing model, three valid voters; unanimity is explicitly among responding voters. |
| SYN16 | Invalid JSON corrected on the single allowed retry; both attempts retained. |
| SYN17 | Failed JSON plus abstention leaves two votes: insufficient participation, context requested. |
| SYN18 | One abstention with secondary hypotheses preserved and three valid votes. |
| SYN19 | Past versus unknown temporal interpretation produces a tie. |

`farajamh.pilot.simulate` submits explicit simulation payloads through the real permission/state methods. Simulated profiles remain in every decision, and exported filenames/titles state `SIMULATED — NOT FOR RELEASE`. The driver never alters an account to pretend to be human. Normal `run`/`batch` do not execute this driver and stop awaiting review.

The final executed snapshot is `evidence/pilot-final/`. Earlier `pilot-01` and `pilot-validation*` directories are retained development snapshots, with earlier code/input hashes and catalog formats; use the final snapshot for acceptance. All model-runtime values are actual measured fixture-processing time, not inference benchmarks. Run timestamps and runtimes vary, while fixture outputs and semantic vote results are deterministic.

| Metric | Executed result | Denominator / meaning |
|---|---:|---|
| Selected configurations | 80 | 20 utterances × 4 configurations |
| Completed schema-valid outputs | 78 | Includes two abstentions; 78/80 selected |
| Failed configurations | 2 | 2/80, after failure/retry handling |
| Abstaining outputs | 2 | 2/78 completed; no primary votes |
| Primary votes | 76 | Completed outputs with a non-null primary |
| Ties | 4 / 20 (20%) | All utterances; no invented minority winner |
| No-majority | 2 / 20 (10%) | Unique top group below strict majority |
| Majority with dissent | 2 / 20 | Three primary supporters and one dissent |
| Unanimous among voters | 11 / 20 | Participation separately reported |
| Insufficient participation | 1 / 20 | Fewer than three eligible primary votes |
| Substantive dissent | 8 / 20 (40%) | Different contextual signatures or differing risk signals |
| Dissent retained | 28 / 28 (100%) | Original primary hypotheses assigned to minority/competing groups; all secondary hypotheses/raw attempts additionally retained |
| Each resource lookup hit rate | 4 / 18 (22.22%) | At least one fictional hit per adjudicated utterance/resource search |
| Each resource lookup failure rate | 0 / 18 | `UNAVAILABLE`/`SEARCH_FAILED`; separately tested failure scenarios are not pilot successes |
| Each resource no-results | 14 / 18 | Successful searches with no fictional candidates |
| Simulated reviewer minority selection | 2 / 40 (5%) | Submitted simulated review decisions, not unique reviewers |
| Simulated arbitrator override | 1 / 13 (7.69%) | Adjudicated items with a model-majority group; accepted meaning differs from every majority meaning |
| Simulated adjudicator outcomes | 17 approve, 1 multiple, 1 unresolved, 1 context request | All twenty sign-offs; sign-off does not imply resolved meaning |
| Unresolved/context-requested | 2 | Excluded from adjudicated synthetic subset and mappings |
| Scoped gap decisions | 9 | Active resource × curated-sense gap records; not nine distinct expressions |
| Curated local senses | 4 | Explicit simulated curation; no one-concept-per-utterance rule |
| Demonstration mapping rows | 3 | Fictional targets, approved `skos:relatedMatch`; no real SNOMED verification |
| Review completion | 20 / 20 | Items with an arbitrator decision, including unresolved decisions |
| Real reviewer metrics | **NOT MEASURED** | No actual reviewers or arbitrators took part |

Fleiss' kappa is **0.659404** across **17 eligible items**, using each model's primary distress category. Three items are excluded because of missing/failed/abstaining primary ratings. The fixed panel is the same four configuration IDs in the same order; they are treated as four raters for this software calculation, not claimed to be statistically independent humans. Observed pair agreement is 0.803922, chance agreement 0.424308. Kappa is undefined when there are no eligible items or expected agreement is one. It is not reported as a meaningful single-utterance statistic. Categorical agreement can differ from contextual-semantic agreement, particularly when qualifiers differ inside one distress category.

Runtime per model/utterance is recorded in `metrics.json` as seconds from start through all attempts; per-utterance runtime is the sum of these sequential calls. It excludes later human review waiting and terminology import time. These mock metrics establish voting/state/export software behavior only; none measure cultural correctness, clinical validity or real model accuracy.

Demonstration SSSOM rows use `semapv:UnspecifiedMatching` because there was no actual human curation. `semapv:ManualMappingCuration` is reserved for actual human-curated research releases; detailed simulated decisions remain explicit in the sidecar.
