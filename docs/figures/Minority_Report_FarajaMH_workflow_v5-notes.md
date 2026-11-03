# The Minority Report · FarajaMH — v5 notes

V5 replaces the five-band overview with eight equal cards in two rows of four. It removes the subtitle, keeps models blind to dictionary evidence during their first pass, and places optional human arbitration inside HITL Review. No application behavior was changed.

## Worked example
The phrase “Moyo wangu unaniuma” comes from the proposed illustration in the discussion. The surrounding bereavement context, dictionary entry, model proposals and reviewer conclusion in v5 are invented for demonstration. They are not workshop evidence, verified Swahili interpretations, actual model outputs or a real clinical assessment.

The example illustrates emotional and physical readings, preserves their disagreement, and ends with an illustrative local meaning while external mapping remains pending. A physical reading remains documented; no diagnosis, questionnaire score, code or export is inferred from the phrase.

## LOINC check
LOINC 44255-8 is an active term named “Feeling down, depressed, or hopeless in last 2 weeks” and is a member of the PHQ-9 panel. Verifying the identifier does not verify that this expression maps to it. The image therefore omits that code and shows external mapping as pending.

Source: https://loinc.org/44255-8

## SSSOM and OMOP
SSSOM records semantic relationships, justification and provenance. It is not a patient-outcome record. The image's SSSOM-to-OMOP sequence is a proposed implementation: only suitable mappings, with validated relation semantics and targets, can support OMOP mapping. SSSOM by itself does not require that sequence.

OMOP custom local concepts have identifiers above 2,000,000,000 and are non-standard. An approved FarajaMH local sense is not automatically an OMOP custom concept or a Standard Concept.

Sources:
- https://mapping-commons.github.io/sssom/1.0/
- https://ohdsi.github.io/CommonDataModel/customConcepts.html

## Review and workflow
The sequence across the cards is explanatory reading order. The independent model pass occurs before dictionary exposure; presenting dictionary evidence in the next card is not an instruction to pass it into that first model call.

HITL includes R1 meaning/category, R2 terminology relationships and R3 final check/submission. Optional human second opinion returns to R3; if it changes meaning or mapping, the appropriate qualified reviewer must recheck the change before final submission. A single person can cover R1 and R2 only if qualified for both.

All disagreements, all safety flags and a random sample of agreed cases go to review under a sampling protocol still to be agreed. Remaining agreed cases retain unreviewed proposals without approved mappings or exports. Safety remains separate from the primary category.

The row-wrap connector is a reading-order continuation; its repeat label indicates that steps 3–7 are carried out separately for each expression. It is not a model voting loop.

## Questions still for Jay and the team
1. Dictionary seed: workshop library, external sources, or both? Who assigned and maintains the classes?
2. Does the intended OMOP/SSSOM sequence select OMOP targets before recording them, or transform suitable approved records from a SSSOM registry?
3. Confirm the role of humans and any LLM assistance in arbitration.
4. Agree the sample size/rate and selection method for agreed cases.
5. Reconcile category labels with the actual workshop codebook.
6. Have competent language and domain reviewers verify the example before presenting it as evidence.

The proposal footer remains because neither this diagram nor its mock example establishes an adopted or implemented project method.

