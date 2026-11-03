"""Constructed software fixtures, never evidence of community usage or real model behavior."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "pilot"
OUT.mkdir(exist_ok=True)
MODEL_IDS = ["small-qwen", "small-llama", "medium-gemma", "comparison-qwen"]
ITEMS = [
    ("My heart is burning", "A synthetic speaker discusses a loss and also mentions discomfort after a meal.", "en", "emotional pain", "somatic", "TIED"),
    ("Moyo unauma", "The synthetic speaker mentions missing a friend; physical discomfort has not been excluded.", "sw", "emotional pain", "somatic", "MAJORITY_WITH_DISSENT"),
    ("Kichwa kinawaka moto", "After a difficult workday, the speaker mentions heat and many unfinished tasks.", "sw", "overwhelmed", "somatic", "NO_MAJORITY"),
    ("Mawazo mengi", "The synthetic speaker is worried about an upcoming examination.", "sw", "worry", "social", "UNANIMOUS"),
    ("Sina mawazo mengi leo", "The speaker explicitly denies being troubled today.", "sw", "denied worry", "emotional", "UNANIMOUS"),
    ("Anasema moyo unauma", "A speaker reports another synthetic person's words; referent remains uncertain.", "sw", "reported emotional pain", "emotional", "TIED"),
    ("I want to disappear, nimechoka", "Synthetic ambiguous wish to get away. One fixture model raises possible self-harm; others read fatigue.", "sw-en", "fatigue", "emotional", "MAJORITY_WITH_DISSENT"),
    ("Sitaki kuamka kesho", "A synthetic speaker mentions dread about tomorrow; urgency is uncertain.", "sw", "dread", "emotional", "UNANIMOUS"),
    ("Nawaza kujidhuru", "Explicit synthetic self-harm statement for review queue testing only.", "sw", "possible urgent distress", "emotional", "UNANIMOUS"),
    ("Moyo unaruka kwa furaha", "A synthetic celebration after receiving good news.", "sw", "joy", "non_distress", "UNANIMOUS"),
    ("This chilli is fire, tamu sana", "A synthetic speaker enjoys a spicy meal; no distress is described.", "en-sw", "enjoyment of food", "non_distress", "UNANIMOUS"),
    ("Nimechoka, kazi imekuwa nyingi", "A synthetic speaker describes tiredness following a long workday.", "sw", "work fatigue", "emotional", "UNANIMOUS"),
    ("Niko sawa, lakini sijui", "A synthetic speaker gives an uncertain answer when asked how they feel.", "sw", "uncertain state", "uncertain", "NO_MAJORITY"),
    ("Roho yangu haina amani", "A synthetic speaker uses a spiritual expression without further explanation.", "sw", "spiritual unease", "spiritual", "TIED"),
    ("Stress iko juu leo", "Constructed code-switching about today's workload; no validated Sheng attribution.", "en-sw", "work stress", "social", "UNANIMOUS"),
    ("Ninahisi mzigo moyoni", "A synthetic speaker describes sadness after an argument.", "sw", "sadness", "emotional", "UNANIMOUS"),
    ("Sijui kueleza hii hali", "A synthetic speaker cannot describe the situation; two models are unusable/abstaining.", "sw", "uncertain description", "uncertain", "INSUFFICIENT_PARTICIPATION"),
    ("I feel low, lakini nitaongea baadaye", "A synthetic speaker postpones discussion of feeling low.", "en-sw", "low mood", "emotional", "UNANIMOUS"),
    ("Nilikuwa na mawazo mengi mwaka jana", "A synthetic speaker refers to worry last year; current experience is not stated.", "sw", "past worry", "emotional", "TIED"),
    ("Mawazo mengi kuhusu sherehe", "The synthetic speaker happily plans a celebration with many ideas.", "sw", "celebration planning", "non_distress", "UNANIMOUS"),
]
GLOSSES = [
    "My heart is burning", "The heart hurts", "The head is burning with fire", "Many thoughts",
    "I do not have many thoughts today", "They say the heart hurts", "I want to disappear, I am tired",
    "I do not want to wake up tomorrow", "I am thinking of harming myself", "The heart is jumping with joy",
    "This chilli is fire, very tasty", "I am tired, work has been a lot", "I am okay, but I do not know",
    "My spirit has no peace", "Stress is high today", "I feel a burden in the heart",
    "I do not know how to explain this state", "I feel low, but I will talk later",
    "I had many thoughts last year", "Many thoughts about the celebration",
]


def build():
    records, responses, expected = [], {}, {}
    for i, (text, context, lang, experience, alternate_category, state) in enumerate(ITEMS, 1):
        uid = f"SYN{i:02}"
        qualifiers = {"experiencer": "SYN-person", "assertion": "affirmed", "attribution": "self", "event_time": "present",
            "utterance_time": "2026-01-01T12:00:00Z", "setting": "synthetic interview"}
        if i == 5: qualifiers["assertion"] = "negated"
        if i == 6: qualifiers.update(experiencer="SYN-other", attribution="reported")
        if i == 19: qualifiers["event_time"] = "past year"
        if i == 13: qualifiers["assertion"] = "uncertain"
        source = {"schema_version": "1.0", "utterance_id": uid, "synthetic": True, "original_text": text,
            "language": "mul" if "-" in lang else lang, "language_spans": [], "source_type": "constructed-text", "speaker_role": "synthetic narrator",
            "speaker_ref": "SYN-person", "region_variety": None, "conversation": context, "qualifiers": qualifiers,
            "evidence": [{"id": "E1", "text": context, "reference": "synthetic-fixture:" + uid}]}
        if i in (7, 11, 15, 18):
            boundary = text.index({7: "nimechoka", 11: "tamu", 15: "iko", 18: "lakini"}[i])
            source["language_spans"] = [{"start": 0, "end": boundary, "language": "en", "status": "hypothesis"},
                {"start": boundary, "end": len(text), "language": "sw", "status": "hypothesis"}]
        records.append(source)
        outputs = {}
        for j, model in enumerate(MODEL_IDS):
            category = alternate_category if i in (10, 11, 20, 13, 17, 14, 15) else "emotional"
            exp = experience
            if state == "TIED" and j >= 2:
                exp = "physical burning sensation" if i == 1 else ("different attributed experiencer" if i == 6 else "different contextual reading")
                category = alternate_category
            if state == "MAJORITY_WITH_DISSENT" and j == 3:
                exp, category = ("physical pain", "somatic") if i == 2 else ("possible desire for absence", "uncertain")
            if state == "NO_MAJORITY" and j >= 2:
                exp, category = ("physical heat" if j == 2 else "social pressure"), ("somatic" if j == 2 else "social")
            h = {"id": "h1", "meaning": exp, "category": category,
                "semantic_frame": {"experience": exp, "cause": "contextual possibility", "cultural_reading": "not established"},
                "qualifiers": copy.deepcopy(qualifiers), "search_terms": [exp], "evidence_refs": ["E1"],
                "rationale": "Illustrative fixture reading of E1; not a verified cultural fact.",
                "counterevidence": ["Alternative readings may remain plausible"], "uncertainty": "Constructed unvalidated interpretation",
                "cultural_notes": []}
            if i == 6 and j >= 2: h["qualifiers"]["experiencer"] = "unknown"
            if i == 19 and j >= 2: h["qualifiers"]["event_time"] = "unknown"
            response = {"schema_version": "1.0", "literal_gloss": GLOSSES[i - 1],
                "contextual_rendering": exp, "hypotheses": [h], "primary_hypothesis": "h1",
                "risk": {"signal": "flagged" if (i == 7 and j == 3) or i == 9 else ("uncertain" if i == 8 else "not_flagged"),
                    "evidence_refs": ["E1"], "rationale": "Synthetic risk routing example"},
                "questions": ["What additional context would clarify this reading?"], "confidence_uncalibrated": None}
            if i == 15 and j == 3: outputs[model] = [{"fixture_failure": True}]
            elif i == 16 and j == 0: outputs[model] = ['{"invalid":', response]
            elif i == 17 and j == 0: outputs[model] = ['{"invalid":', '{"still_invalid":']
            elif (i == 17 and j == 1) or (i == 18 and j == 3):
                response["primary_hypothesis"] = None
                outputs[model] = [response]
            else: outputs[model] = [response]
        responses[uid] = outputs
        expected[uid] = state
    (OUT / "utterances.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    for name, value in (("model_responses.json", responses), ("expected.json", expected), ("manifest.json", {
        "schema_version": "1.0", "synthetic": True, "dataset": "utterances.jsonl", "count": 20,
        "description": "Constructed, unvalidated Kiswahili/code-switching examples and deterministic model fixtures. No Sheng authenticity claim.", "community_validated": False})):
        (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__": build()
