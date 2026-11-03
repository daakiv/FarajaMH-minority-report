"""Read workshop sources without changing them; build isolated synthetic test material."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import copy
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_sheets(path):
    with ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(t.text or "" for t in item.findall(".//s:t", NS))
                      for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        result = {}
        for sheet in ET.fromstring(archive.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS):
            target = rels[sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            cells = {}
            for cell in ET.fromstring(archive.read(target)).findall(".//s:sheetData/s:row/s:c", NS):
                value = cell.find("s:v", NS)
                value = value.text if value is not None else "".join(t.text or "" for t in cell.findall(".//s:t", NS))
                if cell.get("t") == "s":
                    value = shared[int(value)]
                cells[cell.get("r")] = value or ""
            result[sheet.get("name")] = cells
        return result


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def build(workbook, slides):
    out = ROOT / "pilot/workshop-dummy"
    out.mkdir(parents=True, exist_ok=True)
    sheets = read_sheets(workbook)
    info, listing = sheets["Info"], sheets["Free listing"]
    provenance = {"workbook": {"filename": workbook.name, "sha256": hashlib.sha256(workbook.read_bytes()).hexdigest()},
                  "slides": {"filename": slides.name, "sha256": hashlib.sha256(slides.read_bytes()).hexdigest()},
                  "review_status": "WORKSHOP_REFERENCE_NOT_VALIDATED_DICTIONARY",
                  "code_convention": "Workbook Cs and Ob retained by user instruction; R kept separately",
                  "diagnostic_labels": "Workshop DAP/comorbidity annotations are not verified patient diagnoses or gold labels"}
    rows = [{"source_row": r, "cells": {col: listing.get(f"{col}{r}", "") for col in "ABCDEFGHIJ"}}
            for r in range(2, 50) if listing.get(f"B{r}")]
    save(out / "workshop-reference.json", {"provenance": provenance, "rows": rows})
    families = [{"source_range": f"Info!B{r}:F{r}", "code": info.get(f"B{r}", ""),
                 "family": info.get(f"C{r}", ""), "primary_category": info.get(f"D{r}") or None,
                 "question": info.get(f"E{r}", ""), "definition": info.get(f"F{r}", ""),
                 "role": "separate_safety_flag" if r == 19 else "family",
                 "slide_code": "Cx" if r == 17 else "S" if r == 18 else info.get(f"B{r}", "")}
                for r in range(10, 20)]
    save(out / "category-reference.json", {"provenance": provenance, "families": families,
         "unresolved": ["Workbook Ob primary category is blank; do not infer it from the slide."]})
    # Every context, interpretation and expected behaviour below is invented for software testing.
    # Row references identify expression wording only, never validate an interpretation.
    specifications = [
        (4, None, "The fictional speaker describes repeatedly thinking about unfinished tasks.", "persistent thoughts about tasks", "C", "Cognitive: Thinking too much", "other", "agreement", "not_flagged"),
        (18, None, "The fictional speaker explains that 'down' means feeling sad after a loss.", "sadness after loss", "E", "Sadness, grief, hopelessness", "emotional", "agreement", "not_flagged"),
        (11, None, "The fictional speaker reports physical chest heaviness and also sadness. The intended sense is unresolved.", "physical chest heaviness", "S", "Head, brain, somatic heat", "somatic", "model_disagreement", "uncertain"),
        (35, None, "The fictional speaker describes a spiritual explanation for reluctance, without further context.", "spiritual attribution of reluctance", "Sp", "Spirit, ancestral, witchcraft", "spiritual", "agreement", "not_flagged"),
        (6, None, "The fictional speaker uses this phrase for feeling confused. Severity and functional impact are unknown.", "confusion needing clarification", "Cl", "Madness, severe disturbance", "uncertain", "model_dictionary_disagreement", "not_flagged"),
        (2, None, "The fictional speaker cannot describe the experience and asks for time to explain.", "meaning needs more context", "Cs", "Context-specific", "uncertain", "model_disagreement", "not_flagged"),
        (30, None, "The fictional speaker describes bodily shaking sensations without a specified location.", "internal bodily shaking sensation", "Ob", "Other bodily", "somatic", "agreement", "not_flagged"),
        (46, None, "In this invented case the speaker also explicitly reports thoughts of self-harm. No method is described.", "distress with a separate safety concern", "E", "Sadness, grief, hopelessness", "emotional", "agreement", "flagged"),
        (16, None, "The fictional speaker reports a racing heart before a difficult conversation. A cause is not established.", "racing-heart sensation", "Ob", "Other bodily", "somatic", "model_disagreement", "uncertain"),
        (17, None, "The fictional speaker is joking about a phone battery, not describing personal distress.", "ordinary device-battery comment", "Cs", "Context-specific", "non_distress", "model_dictionary_disagreement", "not_flagged"),
        (None, "My thoughts keep circling the same task.", "Invented English expression. The speaker repeatedly returns to an unfinished task.", "repetitive task-related thinking", "C", "Cognitive: Thinking too much", "other", "dictionary_missing", "not_flagged"),
        (None, "I do not feel that heaviness now.", "Invented English expression. A previous feeling is explicitly denied in the present.", "present heaviness denied", "E", "Sadness, grief, hopelessness", "emotional", "applicability_negation", "not_flagged"),
        (None, "She said her heart felt heavy.", "Invented quotation. The reported feeling belongs to another fictional person, not the speaker.", "reported emotional heaviness in another person", "E", "Heart-centred", "emotional", "applicability_experiencer", "not_flagged"),
        (None, "My head felt hot last year.", "Invented retrospective statement. No current sensation is asserted.", "past head-heat sensation", "S", "Head, brain, somatic heat", "somatic", "applicability_time", "not_flagged"),
        (None, "My heart feels heavy and my thoughts keep circling.", "Invented sentence containing two expression occurrences. Preserve their shared context.", "emotional heaviness and repetitive thoughts", "E", "Heart-centred", "emotional", "multiple_expression_spans", "not_flagged"),
        (None, "I feel an unfamiliar flicker inside.", "Invented expression deliberately absent from the dummy dictionary. The experience is unclear.", "unresolved unfamiliar experience", "Cs", "Context-specific", "uncertain", "dictionary_missing", "not_flagged"),
    ]
    template = json.loads((ROOT / "examples/source.json").read_text())
    model_template = json.loads((ROOT / "pilot/model_responses.json").read_text())["SYN01"]["small-qwen"][0]
    model_ids = ["small-qwen", "small-llama", "medium-gemma", "comparison-qwen"]
    cases, inputs, entries, model_responses = [], [], [], {}
    for index, (row, wording, context, meaning, code, family, legacy_category, scenario, risk) in enumerate(specifications, 1):
        uid = f"DUMMY_WC_{index:02d}"
        expression = wording if row is None else listing[f"B{row}"]
        source = copy.deepcopy(template)
        source.update(utterance_id=uid, original_text=expression, language="en" if row is None else "und",
                      speaker_ref=f"SYN-{uid}", conversation=context)
        source["qualifiers"].update(experiencer=f"SYN-{uid}", utterance_time="2026-10-10T09:00:00Z")
        if scenario == "applicability_negation": source["qualifiers"]["assertion"] = "negated"
        if scenario == "applicability_experiencer": source["qualifiers"].update(experiencer="SYN-other-person", attribution="other")
        if scenario == "applicability_time": source["qualifiers"]["event_time"] = "past"
        source["evidence"] = [{"id": "E1", "text": context, "reference": f"synthetic-fixture:{uid}"}]
        inputs.append(source)
        origin = f"Free listing!B{row}" if row else "Invented English test wording"
        entry_id = None if scenario == "dictionary_missing" else f"DUMMY_DICT_{index:02d}"
        if entry_id:
            entries.append({"id": entry_id, "version": "dummy-0.1", "expression": expression,
                            "meaning": "test-only incompatible library sense" if scenario == "model_dictionary_disagreement" else meaning,
                            "family": family, "category_code": code, "context_limits": context,
                            "source": origin, "synthetic": True, "approval_status": "SIMULATED_NOT_APPROVED",
                            "external_mapping": None})
        cases.append({"id": uid, "expression": expression, "expression_origin": origin, "synthetic_context": context,
                      "test_meaning": meaning, "proposed_family": family, "category_code": code,
                      "risk_flag": risk, "scenario": scenario, "dictionary_entry_id": entry_id,
                      "synthetic": True, "interpretation_validated": False,
                      "expected_behaviour": "Review every disagreement and safety flag; otherwise apply agreed-case sampling only after dictionary/category/applicability checks.",
                      "legacy_model_category": legacy_category})
        model_responses[uid] = {}
        for model_index, model in enumerate(model_ids):
            output = copy.deepcopy(model_template)
            chosen = "alternative unresolved reading" if scenario == "model_disagreement" and model_index == 3 else meaning
            output.update(literal_gloss="UNVALIDATED dummy gloss: " + meaning, contextual_rendering=chosen)
            h = output["hypotheses"][0]
            h.update(meaning=chosen, category=legacy_category, qualifiers=copy.deepcopy(source["qualifiers"]), search_terms=[chosen])
            h["semantic_frame"]["experience"] = chosen
            output["risk"]["signal"] = risk
            model_responses[uid][model] = [output]
    save(out / "cases.json", {"version": "dummy-0.1", "source_provenance": provenance, "cases": cases})
    save(out / "dictionary.json", {"version": "dummy-0.1", "synthetic": True, "curator_approved": False, "entries": entries})
    save(out / "model_responses.json", model_responses)
    (out / "utterances.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in inputs))
    save(out / "manifest.json", {"schema_version": "1.0", "synthetic": True, "dataset": "workshop-inspired-dummy-0.1",
         "count": len(inputs), "description": "Workshop wording with invented contexts plus invented English controls. No validated meanings or diagnoses.", "community_validated": False})
    save(out / "pilot-decisions.json", {"status": "USER_PROPOSED_TEST_SETTINGS_NOT_RUNTIME_CONFIGURATION",
         "agreed_case_sampling_rate": 0.1, "sampling_protocol": "pending", "meaning_reviewers": 1,
         "same_trained_reviewer_covers_terminology": True, "code_convention": "workbook_Cs_Ob",
         "risk_is_separate": True, "dictionary_curator_role": "pending clarification",
         "second_opinion_role": "pending clarification", "project_adopted": False})
    print(f"Preserved {len(rows)} workshop rows and {len(families)} definitions; built {len(cases)} synthetic cases and {len(entries)} dummy dictionary entries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("slides", type=Path)
    args = parser.parse_args()
    build(args.workbook, args.slides)
