# The Minority Report · FarajaMH — v4 editorial notes

This version follows the requested five-band overview. It changes the infographic only; it does not implement a new application workflow.

## Reading and routing
Input → gather → compare and route → HITL Review → outputs.
The review band contains R1 → R2 → R3, with an optional human second opinion returning to R3. If the advice changes the meaning or a mapping, the relevant qualified reviewer must recheck that change before R3 finalizes the decision.

Cases selected for HITL are all disagreements, all safety flags, and a protocol-defined random sample of agreed cases. Other agreed cases remain unreviewed proposals and do not enter approved mapping/export outputs. Safety assessment is separate from the primary category.

The requested connector plan contains 12 solid arrows, 2 dashed orange arbitration arrows and 1 dashed teal dictionary-feedback arrow. The dashed enclosure marks repetition and is not a connector. Arbitration is an explicit exception to forward-only reading.

## SSSOM → OMOP is a proposed project sequence
SSSOM represents semantic mapping assertions, their relation, justification and provenance. It does not itself impose an OMOP processing order, create patient outcomes or make a related/broader/narrower concept interchangeable with an OMOP Standard Concept.

For this proposed implementation, qualified people approve mappings, those mappings are recorded in SSSOM, and an explicitly validated transformation can use suitable records to populate OMOP vocabulary mappings. A mapping to an OMOP target can already identify the OMOP ID in the SSSOM record. The arrow denotes processing, not a claim that every SSSOM relationship can automatically become an OMOP mapping.

Reference: https://mapping-commons.github.io/sssom/1.0/

## Local OMOP identifiers
The range above 2,000,000,000 is for locally defined custom, non-standard OMOP concepts. It is not the ID range for all OMOP concepts, and a FarajaMH local concept does not receive an OMOP ID merely by being approved. Custom source concepts and standard target concepts must remain distinct.

Reference: https://ohdsi.github.io/CommonDataModel/customConcepts.html

## Provisional decisions for Jay and the team
1. Is the workshop library the dictionary seed, supplemented by external sources, and who curates its categories?
2. Does Jay intend OMOP target selection followed by SSSOM recording, or a governed SSSOM registry transformed into OMOP vocabulary tables? The image shows the second as a proposed processing sequence.
3. Confirm that final arbitration is human; an LLM can assist but is not the accountable signatory in this design.
4. Define the sampling rate and method for model-agreed cases.
5. Reconcile the primary category list with the workshop codebook, keeping safety separate.
6. Specify which permitted and required downstream use, if any, calls for OMOP export.

Questionnaire links identify related item content, not a respondent's answer or a score. The Swahili worked example is intentionally left to a separately verified companion sheet.

