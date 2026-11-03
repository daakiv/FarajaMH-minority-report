# The Minority Report · FarajaMH — v3 design decisions

This is a proposed workflow infographic, not a change to the running application or an adopted project protocol.

## Dictionary source
Proposed seed: the FarajaMH workshop expression library. Its entries and category definitions require curator review before being labelled validated dictionary evidence. Each entry should retain original wording, language/dialect, meaning alternatives, category, applicability limits, source and version. Additional dictionaries and community contributions should be added through governed curation, with provenance and permissions recorded. An unmatched expression remains eligible for interpretation; dictionary absence is not counterevidence.

## Models
Use separate first-pass calls with the original expression and context before exposing models to dictionary entries. Separate calls do not establish statistical independence. Record model identifiers, versions and prompt versions. Compare the proposals with one another and with retrieved dictionary evidence. Preserve minority hypotheses and the evidence behind them; do not decide by vote.

## Routing and review
The proposed rule selects every disagreement, every safety flag and a random sample of agreed cases. The project must define the sample rule and review capacity. Other agreed cases remain model-agreed, unreviewed, without approved mapping exports. A safety flag requires assessment even when models agree.

R1 establishes contextual meaning and category using clinical, cultural and linguistic expertise. R2 reviews concept relationships with terminology expertise. One person can cover both only if qualified. R3 checks completeness and submits the versioned decision.

An optional arbitrator is a human expert, not an LLM decision-maker. Arbitration is triggered by unclear, challenged or unresolved decisions, not automatically by choosing a minority model proposal. Advice returns to R1 or R2 for rechecking before R3. Unresolved meaning blocks concept approval; unresolved external mapping need not invalidate an approved local meaning.

## Ontology, OMOP and SSSOM
Establish the contextual meaning and a local concept, then review relationships to relevant ontologies/terminologies. Where suitable, map into OMOP Standard Concepts; export OMOP data only if required by the project and supported by an agreed data model. Do not equate an ontology relationship such as a broad match with a valid equivalent OMOP mapping.

SSSOM records approved mapping assertions and their relation, justification and provenance. It can record ontology mappings even without an OMOP match. Additional OMOP mappings can also have SSSOM records. A valid local concept may remain without an external match.

References: [OHDSI SOURCE_TO_CONCEPT_MAP](https://ohdsi.github.io/CommonDataModel/cdm55.html#source_to_concept_map), [SSSOM specification](https://mapping-commons.github.io/sssom/1.0/).

## Categories, questionnaires and examples
The category scheme is provisional pending reconciliation with the workshop codebook. Risk/safety is separate from the primary interpretation category. PHQ-9 and GAD-7 links via LOINC identify item content; they do not establish an answer, time window, frequency, score or diagnosis.

The proposed “Moyo wangu unaniuma” example is omitted pending competent language review and verification of its source evidence, contextual readings and concept identifiers. A companion sheet should be produced after those checks rather than presenting invented mappings as validated.

## Feedback
Reviewer corrections propose dictionary changes. A curator approves them and publishes a new dictionary version; individual reviews never silently overwrite dictionary entries.

