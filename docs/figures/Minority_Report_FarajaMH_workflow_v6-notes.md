# The Minority Report · FarajaMH — v6 design notes

V6 adds a distinct terminology lookup and sign-off stage after human approval of contextual meaning. It edits the infographic only, not the application.

## Recommended responsibility boundary
Minority Report should manage expression context, model proposals, dictionary comparison, routing, human decisions and their provenance. A terminology component/service should retrieve candidates and their source releases using the approved contextual meaning. R2 remains responsible for approving relationships, recording semantic gaps or deferring.

The component can run inside the same application initially. It does not have to be deployed as a separate network service. The graphic says “from the terminology service” to clarify responsibility without claiming a separately deployed service exists.

The current prototype already calls Resolver.all after adjudication, using search_terms from the accepted meanings (farajamh/pipeline.py). Its current required resources are MFOEM, MFOMD and SNOMED_CT (farajamh/common.py). LOINC and OMOP candidate retrieval in v6 are proposed extensions, not verified current integrations.

## Stage boundary
6: R1 approves meaning and category, with safety assessment and an optional human second opinion. Unresolved meaning requests context; it must not be silently passed to concept approval.
7: Automated lookup uses approved meaning, contextual qualifiers and supported search terms. R2 checks candidate definitions, applicability, source release and relationship semantics. Candidate ranking is not mapping confidence. A related match does not assert equivalence; broader/narrower relations should be represented where appropriate rather than forced into an exact match.
8: R3 checks and records the versioned decisions and approved mapping assertions. Suitable validated mappings may feed the proposed SSSOM-to-OMOP processing route. Dictionary corrections remain proposals until curator approval, followed by a new version.

“Emotional pain linked to grief” is a more contextually directed query than the raw idiom in this example, but it cannot guarantee appropriate retrieval. The raw expression and its evidence remain linked for audit and human review. A lookup outage or unavailable terminology is not evidence of a semantic gap.

## Consistent invented example
The expression is “Moyo wangu unaniuma”. The grief/chest-discomfort context, dictionary entry, model readings and human conclusion are fabricated for illustration. Model A/B/C are mock outputs, not measurements of real models.

The illustrative emotional meaning does not clear the reported chest-pain concern. That concern remains on a separate assessment track. The example's external mapping remains pending and no external mapping or export is depicted as approved.

## Confidence and routing
Record any model-reported confidence with its origin and method. Do not present it as measured accuracy or use it as this design's routing criterion. Route all disagreements and safety flags plus a protocol-defined random sample of agreed cases. Other agreed cases remain unreviewed proposals.

## Terminology facts already checked
LOINC 44255-8 identifies “Feeling down, depressed, or hopeless in last 2 weeks” and belongs to the PHQ-9 panel. This does not establish a mapping from the example expression. No clinical identifier is printed in the example.

Source: https://loinc.org/44255-8

Custom local OMOP concepts have identifiers above 2,000,000,000 and are non-standard; this does not describe all OMOP identifiers. SSSOM records mapping assertions, justification and provenance; it is not a patient-outcome record and does not itself mandate an OMOP sequence.

Sources:
- https://ohdsi.github.io/CommonDataModel/customConcepts.html
- https://mapping-commons.github.io/sssom/1.0/

## Still to agree
Dictionary seed and ownership; workshop category codebook; exact SSSOM/OMOP processing order; sampling rate; human arbitration responsibilities; terminology source versions and access; example validation. The diagram remains proposed and not adopted or implemented.

The simplified footer retains the requested rule against using real patient data in consumer chatbots. The removed detailed category and provenance lists remain project requirements to specify, not abandoned requirements.

