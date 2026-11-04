# Authoritative workflow v9.1

Source: [Minority_Report_FarajaMH_workflow_v9_1.png](figures/Minority_Report_FarajaMH_workflow_v9_1.png), supplied by the user on 10 October 2026 (Africa/Nairobi).

SHA-256: `fedae12fe4199e3cbfd370fdcc27ccf766b15fa62a0fab72084dd96566feca33`

The attached image wins over conflicting code and earlier documents. The project has not adopted this approach; testing uses dummy data only. This document describes required behaviour, not implementation completion.

## 1 · Utterance and context

Keep original wording, language or dialect, setting and the source-language record. No translation before interpretation.

## 2 · Identify expressions

Extract each expression as a span. Keep full context; reviewers may correct boundaries. Steps 3–7 run once per expression.

## 3 · Model interpretations

Use separate calls before dictionary exposure. Pin model and prompt versions. Return literal translation, meanings, category and evidence. Record confidence, never use it for routing. The image illustrates Model A, Model B, Model C and more models; it specifies no vendor, deployment tool or fixed model count.

## 4 · Dictionary evidence

A growing, versioned idiom library, with the FarajaMH workshop library as a proposed seed. Entries retain meaning, category, context limits and source. If an entry is missing, continue interpretation and review. Evidence source, not a vote.

## 5 · Compare and route

Compare model–model and model–dictionary interpretations. Check category and applicability: negation, experiencer and time. Review all disagreements, all safety flags and a random sample of agreed cases. Other agreed cases remain unreviewed, with no approved mapping or export. Safety concern is assessed separately.

## 6 · HITL Review: meaning

Qualified reviewers assess meaning and category. Safety assessment remains separate. Seek a second opinion when needed. Unresolved meaning leads to a request for context. The image does not impose a mandatory distinct arbitrator or fixed reviewer quorum.

## 7 · Terminology lookup

Automated candidates come from the terminology service using the approved meaning. Sources shown: MFOEM, MFOMD, SNOMED CT, LOINC (PHQ-9/GAD-7 items), and OMOP standard vocabularies.

Terminologist sign-off: exact, close or related match; record a gap; or defer. A local concept can remain without an external match. Related questionnaire content is not a questionnaire score.

## 8 · Record and outputs

Record a versioned decision. SSSOM is versioned and carries relation, justification and provenance. Suitable validated mappings support OMOP. Custom non-standard local IDs are above 2,000,000,000. Export is optional when required. Retain the reviewed local meaning; no external mapping or export while pending. Mappings are not patient outcomes.

## Dictionary growth

New-entry and correction proposals from steps 6–7 require curator approval before a new dictionary version. No automatic overwrite.

## Evidence boundaries

Dictionary evidence is not a model vote; model agreement is not correctness; concept mapping is not diagnosis. The worked example is illustrative: context, dictionary entry, model outputs and review are invented. Swahili readings and codes need verification. No real patient data in consumer chatbots. This is proposed design, not yet adopted or fully implemented.

The later presentation discussion of diagnosis, training, triage and treatment is not part of this infographic's process. Do not implement it as an additional stage under this specification.

## User clarifications for dummy testing (10 October 2026)

Use the Room C workbook’s Free listing as expression reference and Info as category reference, with the definition slide as supporting material. Retain workbook Cs/Ob codes, preserving slide alternatives as provenance. R stays separate. The user proposed 10% of otherwise-agreed cases for sampling and a trained HITL reviewer covering meaning and terminology. These are prototype design choices, not a claim of project adoption. See the [dummy pack](../pilot/workshop-dummy/README.md) and [alignment register](ALIGNMENT.md) for implemented behaviour and open issues.

On 11 October 2026 the user confirmed one reviewer handling everything. The guided screen supports the same configured identity for meaning, terminology and local curation, while retaining separate decisions and explicit reuse approval. DAP associations remain separate from meaning categories and safety. A requested second opinion still requires another person. Agreed-case sampling is implemented as a configurable test rate (see the [alignment register](ALIGNMENT.md)); agreed cases outside the sample are marked "Agreed, not sampled" and can still be reviewed by choice.
