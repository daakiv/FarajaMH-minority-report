# Workshop-inspired dummy test pack

This is software test material, not an adopted FarajaMH process, validated idiom dictionary, clinical dataset or training gold standard.

The Room C workbook's **Free listing** sheet supplies expression wording. Its **Info** sheet supplies the category reference. The attached category-definition slide is a secondary reference. The original files are unchanged. `workshop-reference.json` preserves all 48 populated listing rows, including duplicates, blanks and original labels. It does not copy facilitator personal details. File names and SHA-256 fingerprints identify both attachments.

## What is invented

`cases.json` contains 16 scenarios: 10 use workshop wording in invented contexts and six use invented English wording. All contexts, test meanings, dictionary meanings, model responses and behavioural expectations are constructed. No claim is made that a model or community endorsed those meanings. No new Sheng expressions are presented as authentic community usage.

`dictionary.json` contains 14 dummy entries, all explicitly **SIMULATED_NOT_APPROVED**. Two cases intentionally have no entry. This fixture is not automatically installed as the live dictionary. Its incompatible senses are deliberate test cases, not corrections to the workshop.

`utterances.jsonl`, `manifest.json` and `model_responses.json` are compatible with the existing synthetic-input/model schemas. The 64 responses simulate four model configurations and require no live model calls. The model schema's legacy categories differ from the workshop codebook; `legacy_model_category` exposes that distinction rather than pretending codes have already been integrated. In particular, the current model schema has no dedicated cognitive or clinical-symptom category.

Coverage includes emotional/physical alternatives, dictionary disagreement, missing entries, uncertainty, separate safety flags despite agreement, negation, another experiencer, past time, ordinary usage and a sentence with two expressions. The last case documents the need for occurrence extraction; the current runtime still processes it as an utterance, not as two implemented expression dossiers.

## Decisions from the user on 10 October 2026

- Keep workbook codes **Cs** and **Ob** for testing. Preserve slide alternatives **Cx** and **S** as provenance. The workbook's primary category for Ob is blank and remains unresolved.
- Keep **R** as a separate safety flag, never as the only meaning category.
- Use **10%** as the proposed test sampling rate for otherwise-agreed cases. All disagreements and all safety flags still receive review. The rounding/randomisation protocol is not yet fixed.
- One trained HITL reviewer is intended to cover meaning and terminology review. This requires appropriate expertise for both tasks. Dictionary-curator permissions and the second-opinion provider remain to be confirmed.

`pilot-decisions.json` records these design decisions. It is **not runtime configuration**. The existing application still uses the older multi-reviewer/arbitrator gates and lacks dictionary comparison and random-sample routing. This pack does not silently relax those controls.

Ten percent is a test workload setting, not statistical validation. The number reviewed, error frequency and desired uncertainty matter. For example, reviewing 10% of 20 agreed cases gives only two reviewed cases. See NIST's [sample-size guidance](https://itl.nist.gov/div898/handbook/prc/section2/prc242.htm). For debugging the small dummy pack, inspect all scenarios; that is a software check, not a change to the proposed 10% operational policy.

## Verification

Run from the repository root:

```sh
.venv/bin/python -m pytest -q tests/test_workshop_dummy.py
```

The tests validate all inputs/responses, preserve workbook code conflicts, check synthetic/approval boundaries, and run the 16 cases through the current model stage without approving a meaning or mapping. They do not claim the complete infographic workflow is implemented.

Rebuild the pack from the two supplied local source files:

```sh
.venv/bin/python tools/build_workshop_dummy.py '/path/to/workshop.xlsx' '/path/to/category-definitions.pptx'
```

The readable companion is `outputs/workshop-dummy/FarajaMH_Workshop_Dummy_Test_Pack.xlsx`. Source diagnostic/comorbidity annotations remain workshop notes, never confirmed diagnoses or automatically accepted training labels.
