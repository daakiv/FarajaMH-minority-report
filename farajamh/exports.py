from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from urllib.parse import urlparse, unquote

import yaml
from openpyxl import Workbook
from rdflib import Graph

from . import __version__
from .common import CATEGORY_FAMILIES, ROOT, RESOURCES, canonical, digest, file_hash, now, require, write_json

SEARCH_PROBLEM = {"SEARCH_FAILED": "the search failed; rerun it", "UNAVAILABLE": "the source was unavailable; rerun the search"}
# Single-reviewer workflow: the approving person is the author; reviewer_id is reserved for a separate check and is omitted.
FIELDS = ["subject_id", "object_id", "predicate_id", "mapping_justification", "subject_label", "subject_category", "object_label",
    "author_id", "mapping_date", "subject_source_version", "object_source", "object_source_version", "mapping_tool", "mapping_tool_version", "comment"]
# Packages exported before subject_category was added still validate.
EARLIER_FIELDS = [f for f in FIELDS if f != "subject_category"]
# One row per exported local concept; joins to the mapping file on subject_id. DAP has no SSSOM slot, so it lives here.
CONCEPT_FIELDS = ["subject_id", "utterance_id", "expression", "language", "family_code", "idiom_family", "dap_categories", "subject_label"]
OBJECT_SOURCES = {"MFOEM": "obo:mfoem.owl", "MFOMD": "obo:mfomd.owl", "SNOMED_CT": "SNOMEDCT:900000000000207008"}
FIELD_DESCRIPTIONS = {
    "utterance_id": "Synthetic case identifier", "original_text": "Original utterance wording, unchanged", "synthetic": "Always true: constructed test data, not patient data",
    "subject_id": "Local FarajaMH concept (curated meaning) being mapped", "object_id": "External terminology concept identifier",
    "predicate_id": "SKOS relationship from the local concept to the external concept", "mapping_justification": "How the mapping was made (SEMAPV term)",
    "subject_label": "English gloss of the local concept", "subject_category": "Idiom family of the local concept, from the workshop coding",
    "expression": "Expression reviewed in the utterance", "language": "Language of the utterance", "family_code": "Workshop idiom family code",
    "idiom_family": "Idiom family name", "dap_categories": "DAP categories chosen by the reviewer, separated by '; '", "object_label": "Label of the external concept", "author_id": "Trained reviewer who approved the mapping",
    "mapping_date": "Date the mapping was approved", "subject_source_version": "Version of the local concept", "object_source": "Terminology the external concept comes from",
    "object_source_version": "Release of that terminology", "mapping_tool": "Software that recorded the mapping", "mapping_tool_version": "Software version",
    "comment": "Reviewer's reason for the relationship"}


def safe_cell(value):
    # Prevent formula execution when reviewers open exported tables.
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: safe_cell(row.get(k, "")) for k in fields} for row in rows)


def review_package(app, uid: str, directory: Path, token: str):
    d = app.view(uid, token)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / f"{uid}.dossier.json", d)
    rows = []
    for run in d["models"]:
        output = run.get("output") or {}
        rows.append({"utterance_id": uid, "version": d["version"], "source": d["source"]["original_text"],
            "context": canonical(d["source"]), "model": run["configuration_id"], "status": run["status"],
            "literal": output.get("literal_gloss", ""), "contextual": output.get("contextual_rendering", ""),
            "hypotheses": canonical(output.get("hypotheses", [])), "attempts": canonical(run["attempts"]),
            "votes_and_dissent": canonical(d["comparison"]), "reviews": canonical(d["reviews"]), "uncertainty": canonical(output.get("questions", []))})
    fields = list(rows[0]) if rows else ["utterance_id", "version", "source", "context"]
    if not rows:
        rows = [{"utterance_id": uid, "version": d["version"], "source": d["source"]["original_text"], "context": canonical(d)}]
    write_csv(directory / f"{uid}.review.csv", rows, fields)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Review package"
    sheet.append(fields)
    for row in rows:
        # Long JSON can exceed Excel's cell limit; full dossier JSON and CSV remain canonical.
        sheet.append([safe_cell(row.get(k, ""))[:32000] for k in fields])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    workbook.save(directory / f"{uid}.review.xlsx")
    return {"directory": str(directory), "dossier_version": d["version"], "xlsx_long_cells": "truncated at 32000 characters; see full JSON/CSV"}


def validate_sssom(path: Path) -> dict:
    """Pinned SSSOM 1.0 application profile: supported slots only; no arbitrary extensions."""
    lines = path.read_text().splitlines()
    meta = yaml.safe_load("\n".join(line[2:] for line in lines if line.startswith("# ")))
    require(meta and all(k in meta for k in ("mapping_set_id", "license", "curie_map")), "SSSOM metadata missing")
    for key in ("mapping_set_id", "license"):
        require(urlparse(meta[key]).scheme in ("http", "https"), "Mapping-set identifiers must be absolute URIs")
    reader = csv.DictReader(io.StringIO("\n".join(line for line in lines if not line.startswith("#"))), delimiter="\t")
    require(reader.fieldnames in (FIELDS, EARLIER_FIELDS), "Unexpected SSSOM profile slots")
    rows = list(reader)
    for row in rows:
        require(all(row.get(k) for k in FIELDS[:4]), "Required SSSOM fields absent")
        for key in ("subject_id", "object_id", "predicate_id", "mapping_justification", "author_id", "object_source"):
            require(":" in row[key] and row[key].split(":", 1)[0] in meta["curie_map"], "Undeclared CURIE prefix")
        require(row["subject_id"].startswith("FARAJA:"), "Mapping subject must be curated sense")
        expected_justification = "semapv:UnspecifiedMatching" if meta.get("mapping_set_title", "").startswith("SIMULATED") else "semapv:ManualMappingCuration"
        require(row["mapping_justification"] == expected_justification, "Justification must distinguish simulated mappings from actual human curation")
        require(row["predicate_id"] in ("skos:exactMatch", "skos:closeMatch", "skos:broadMatch", "skos:narrowMatch", "skos:relatedMatch"), "Unsupported reviewed predicate")
    return {"schema": "SSSOM 1.0", "validator": "farajamh-profile/1.0.0", "rows": len(rows), "metadata": meta}


def mapping_exclusion(app, mapping):
    """Lookup-only experimental targets are omitted, with an explicit release report."""
    resource = mapping["decision"]["resource"]
    if (mapping.get("candidate", {}) or {}).get("experimental_lookup_only") or (mapping.get("resource_metadata", {}) or {}).get("experimental_lookup_only") or app.cfg["terminology"].get(resource, {}).get("experimental_lookup_only"):
        return {"resource": resource, "candidate_id": mapping["decision"].get("candidate_id"),
            "sense_id": mapping["decision"]["sense_id"], "reason": "Experimental lookup-only candidate; excluded from SSSOM mappings"}
    return None


def preview_row(mapping, lookup_only):
    decision = mapping["decision"]
    return {"subject_id": decision["sense_id"], "object_id": decision["candidate_id"], "object_label": (mapping.get("candidate") or {}).get("label"),
        "predicate_id": decision["predicate"], "resource": decision["resource"], "lookup_only": lookup_only}


def export_readiness(app, dossier, person, demonstration=False):
    """Shared recorded-state blockers; export still verifies live releases and targets."""
    blockers, excluded, preview = [], [], []
    flag = (dossier.get("case_flag") or {}).get("status")
    if flag in ("test", "withdrawn"):
        return {"status": "EXCLUDED", "blockers": [], "excluded_mappings": [], "mapping_rows": [],
            "notice": "Marked as " + flag + " case: left out of exports and pilot counts. Its record and decisions are kept."}
    if dossier.get("mode") != app.cfg["mode"]:
        blockers.append("Case mode differs from running configuration")
    if "terminology" not in person.get("roles", []):
        blockers.append("Terminology role required for export")
    if dossier["state"] != "ADJUDICATED":
        blockers.append("Meaning has not been approved")
    if not demonstration and (dossier["mode"] == "fixture" or person.get("simulated")):
        blockers.append("Fixture/simulated approvals cannot produce a research release")
    identities = [r["identity"] for r in dossier.get("reviews", [])]
    if dossier.get("adjudication"):
        identities.append(dossier["adjudication"]["identity"])
    if not demonstration and any(p.get("simulated") for p in identities):
        blockers.append("Simulated meaning review cannot be released")
    for resource in RESOURCES:
        lookup = dossier.get("terminology", {}).get(resource, {})
        if lookup.get("state") not in ("HITS", "NO_RESULTS"):
            blockers.append(resource + ": required terminology review incomplete — " + SEARCH_PROBLEM.get(lookup.get("state"), "not searched yet"))
    senses = {s["id"]: s for s in app.store.senses()}
    for mapping in dossier.get("mapping_reviews", []):
        if mapping.get("stale") or mapping["decision"]["action"] != "approve":
            continue
        exclusion = mapping_exclusion(app, mapping)
        if exclusion:
            # Lookup-only targets never block an export; the test setting only decides which file they appear in.
            if app.cfg["exports"].get("include_lookup_only"):
                preview.append(preview_row(mapping, True))
            else:
                excluded.append(exclusion)
            continue
        sense = senses.get(mapping["decision"]["sense_id"])
        if not sense or not app.sense_current(sense) or sense["version"] != mapping["sense_version"]:
            blockers.append("Curated sense changed: mapping stale")
        if mapping.get("meaning_decision_hash") != (dossier.get("adjudication") or {}).get("decision_hash"):
            blockers.append("Meaning changed: mapping stale")
        if not demonstration and (mapping["identity"].get("simulated") or (sense or {}).get("simulated") or mapping.get("candidate", {}).get("fixture")):
            blockers.append("Simulated curation or fictional candidates cannot be released")
        preview.append(preview_row(mapping, False))
    return {"status": "BLOCKED" if blockers else "READY_FOR_FINAL_CHECK", "blockers": list(dict.fromkeys(blockers)), "excluded_mappings": excluded, "mapping_rows": preview,
        "notice": "Recorded-state check only. Final export checks every eligible case, current resource releases and active targets. No mapping is required to retain an approved local meaning."}


EXPORT_ACTIONS = ("RELEASE_EXPORT", "DEMONSTRATION_EXPORT")


def export_overview(app, person, demonstration=False):
    """Release-level summary for the Record step: what the next export covers and what the last one wrote."""
    # Version numbering matches export_sssom: 1.0.N for the Nth export recorded in the audit.
    history = [{"version": "1.0." + str(n), "timestamp": e["timestamp"], "actor": e["actor"], "package": Path(e["entity"]).name,
        "mapping_rows": e["body"].get("mapping_rows"), "lookup_only_rows": e["body"].get("lookup_only_rows", 0), "cases": len(e["body"].get("versions", {})),
        "excluded_mappings": len(e["body"].get("excluded_mappings", [])), "demonstration": e["action"] == "DEMONSTRATION_EXPORT", "versions": e["body"].get("versions", {})}
        for n, e in enumerate((e for e in app.store.audit() if e["action"] in EXPORT_ACTIONS), 1)][::-1]
    last = history[0] if history else None
    exported = last["versions"] if last else {}
    cases = []
    for d in app.store.all():
        if d["state"] != "ADJUDICATED":
            continue
        # Same eligibility as export_sssom: these cases are skipped by a research release, not blockers.
        identities = [r["identity"] for r in d["reviews"]] + [d["adjudication"]["identity"]]
        if not demonstration and (d["mode"] == "fixture" or any(p["simulated"] for p in identities)):
            continue
        uid, readiness = d["source"]["utterance_id"], export_readiness(app, d, person, demonstration)
        cases.append({"id": uid, "version": d["version"], "status": readiness["status"], "blockers": readiness["blockers"],
            "mapping_rows": len(readiness["mapping_rows"]), "excluded_mappings": len(readiness["excluded_mappings"]), "exported_version": exported.get(uid)})
    history = [{k: v for k, v in h.items() if k != "versions"} for h in history]
    return {"cases": cases, "last_export": history[0] if history else None, "history": history}


def idiom_family(sense) -> tuple[str, str]:
    """Workshop family code and name recorded with the meaning decision; older concepts fall back to the meaning category."""
    code = (sense.get("review_annotations") or {}).get("family_code")
    if code not in CATEGORY_FAMILIES:
        category = (sense.get("meaning") or {}).get("category")
        code = next((k for k, v in CATEGORY_FAMILIES.items() if v[1] == category), None)
    return (code, CATEGORY_FAMILIES[code][0]) if code else ("", "")


def concept_row(sense, source) -> dict:
    code, name = idiom_family(sense)
    span = source.get("expression_span") or {}
    return {"subject_id": sense["id"], "utterance_id": source["utterance_id"], "expression": span.get("text", ""), "language": source.get("language", ""),
        "family_code": code, "idiom_family": name, "dap_categories": "; ".join((sense.get("review_annotations") or {}).get("dap_categories") or []),
        "subject_label": sense["english_gloss"]}


def export_sssom(app, directory: Path, token: str, demonstration: bool = False) -> dict:
    person = app.identity(token, "terminology")
    app.check_mode()
    require(not directory.exists(), "Output directory exists; export a new immutable snapshot")
    require(not demonstration or app.cfg["mode"] == "fixture", "Demonstration export only in fixture mode")
    if not demonstration:
        require(app.cfg["mode"] != "fixture" and not person["simulated"], "Fixture/simulated approvals cannot produce a research release")
    rows, sidecar, assertions, approved_sources, excluded, concepts = [], [], [], [], [], {}
    senses = {s["id"]: s for s in app.store.senses()}
    curies = dict(app.cfg["exports"]["curie_map"])
    curies.setdefault("obo", "http://purl.obolibrary.org/obo/")
    version = "1.0." + str(1 + sum(e["action"] in EXPORT_ACTIONS for e in app.store.audit()))
    lookup_rows, lookup_sidecar = [], []
    # Test setting (exports.include_lookup_only): lookup-only targets such as OLS SNOMED CT go into the main file, labelled per row.
    include_lookup = bool(app.cfg["exports"].get("include_lookup_only"))

    def sssom_row(sense, mapping, candidate):
        decision = mapping["decision"]
        return {"subject_id": sense["id"], "object_id": candidate["id"], "predicate_id": decision["predicate"],
            "mapping_justification": "semapv:UnspecifiedMatching" if demonstration else "semapv:ManualMappingCuration", "subject_label": sense["english_gloss"],
            "subject_category": idiom_family(sense)[1], "object_label": candidate["label"], "author_id": "reviewer:" + mapping["identity"]["id"],
            "mapping_date": mapping["timestamp"][:10], "subject_source_version": str(sense["version"]),
            "object_source": "FIXTURE:" + decision["resource"] if candidate.get("fixture") else OBJECT_SOURCES[decision["resource"]],
            "object_source_version": candidate["release"], "mapping_tool": "farajamh", "mapping_tool_version": __version__, "comment": decision["rationale"]}

    def lookup_only(d, mapping, candidate):
        # Only current decisions: stale concept or meaning changes leave the row out rather than blocking the export.
        sense = senses.get(mapping["decision"]["sense_id"])
        if sense and app.sense_current(sense) and sense["version"] == mapping["sense_version"] and mapping["meaning_decision_hash"] == d["adjudication"]["decision_hash"]:
            lookup_rows.append(sssom_row(sense, mapping, candidate))
            lookup_sidecar.append({"utterance_id": d["source"]["utterance_id"], "dossier_version": d["version"], "decision": mapping, "demonstration": demonstration,
                "lookup_only": True, "curation_notice": "Lookup-only target from a public lookup service, not a licensed release; test use only"})
    dossiers = app.store.all()
    excluded_cases = []
    for d in dossiers:
        if (d.get("case_flag") or {}).get("status") in ("test", "withdrawn"):
            excluded_cases.append({"utterance_id": d["source"]["utterance_id"], "dossier_version": d["version"],
                "status": d["case_flag"]["status"], "reason": d["case_flag"]["reason"]})
            continue
        if d["state"] != "ADJUDICATED":
            continue
        identities = [r["identity"] for r in d["reviews"]] + [d["adjudication"]["identity"]]
        if not demonstration and (d["mode"] == "fixture" or any(p["simulated"] for p in identities)):
            continue
        uid = d["source"]["utterance_id"]
        readiness = export_readiness(app, d, person, demonstration)
        require(not readiness["blockers"], uid + ": " + "; ".join(readiness["blockers"]))
        # Every required resource must have been successfully searched; no forced mapping required.
        for resource in RESOURCES:
            lookup = d["terminology"].get(resource, {})
            require(lookup.get("state") in ("HITS", "NO_RESULTS"), f"{uid} · {resource}: required terminology review incomplete — " + SEARCH_PROBLEM.get(lookup.get("state"), "not searched yet"))
            current = app.resolver.metadata(resource)
            require(digest(current) == digest(lookup["metadata"]), f"{uid} · {resource}: resource version changed; mappings stale")
        for mapping in d["mapping_reviews"]:
            if mapping["stale"] or mapping["decision"]["action"] != "approve":
                continue
            decision = mapping["decision"]
            exclusion = mapping_exclusion(app, mapping)
            if exclusion:
                excluded.append({**exclusion, "utterance_id": d["source"]["utterance_id"], "dossier_version": d["version"]})
                lookup_only(d, mapping, mapping["candidate"])
                continue
            sense = senses[decision["sense_id"]]
            require(app.sense_current(sense) and sense["version"] == mapping["sense_version"], "Curated sense changed: mapping stale")
            require(mapping["meaning_decision_hash"] == d["adjudication"]["decision_hash"], "Meaning changed: mapping stale")
            if not demonstration:
                require(not sense["simulated"] and not mapping["identity"]["simulated"], "Simulated curation cannot be released")
            candidate = app.resolver.verify(decision["resource"], decision["candidate_id"], mapping["candidate"]["iri"])
            if candidate.get("experimental_lookup_only"):
                excluded.append({"utterance_id": d["source"]["utterance_id"], "dossier_version": d["version"],
                    "resource": decision["resource"], "candidate_id": decision["candidate_id"], "sense_id": sense["id"],
                    "reason": "Target verified as experimental lookup-only; excluded from SSSOM mappings"})
                lookup_only(d, mapping, candidate)
                continue
            require(candidate["active"] and candidate["release"] == mapping["candidate"]["release"], f"{uid} · {candidate['id']}: target inactive or release changed")
            require(demonstration or not candidate["fixture"], "Fictional candidate cannot be released")
            prefix, local = candidate["id"].split(":", 1)
            if prefix not in curies:
                require(candidate["iri"].endswith(local), "Cannot declare CURIE from verified IRI")
                curies[prefix] = candidate["iri"][:-len(local)]
            rows.append(sssom_row(sense, mapping, candidate))
            sidecar.append({"row": len(rows), "utterance_id": d["source"]["utterance_id"], "dossier_version": d["version"],
                "decision": mapping, "demonstration": demonstration, "curation_notice": "SIMULATED manual-curation workflow, not human-reviewed" if demonstration else "Actual human curation"})
        source = d["source"]
        assertions.append({"utterance_id": source["utterance_id"], "source_version": d["version"],
            "synthetic": True, "simulated_review": demonstration, "sense_links": [link for link in d["sense_links"]
                if not link.get("stale") and link["id"] in senses and senses[link["id"]]["version"] == link["version"] and app.sense_current(senses[link["id"]])],
            "qualifiers": source["qualifiers"], "adjudicated_meanings": d["adjudication"]["decision"]["meanings"],
            "risk_review_queue": d["priority"]["queue"], "omop_concept_id": None})
        for link in assertions[-1]["sense_links"]:
            if demonstration or not senses[link["id"]]["simulated"]:
                concepts.setdefault(link["id"], concept_row(senses[link["id"]], source))
        approved_sources.append({"utterance_id": source["utterance_id"], "original_text": source["original_text"], "synthetic": "true"})
    require(assertions, "No adjudicated eligible records to export")
    directory.mkdir(parents=True)
    lookup_validation = None
    if include_lookup:
        for row, note in zip(lookup_rows, lookup_sidecar):
            rows.append({**row, "comment": "[Lookup-only " + {"SNOMEDCT:900000000000207008": "SNOMED CT"}.get(row["object_source"], row["object_source"]) + ", test use only] " + row["comment"]})
            sidecar.append({"row": len(rows), **note})
        for item in excluded:
            item["included_for_testing"] = True
    elif lookup_rows:
        # Separate restricted file: kept out of the CC BY mapping set, approved-mappings.csv and the Croissant catalog.
        resources = ", ".join(sorted({r["object_source"] for r in lookup_rows}))
        lookup_title = ("SIMULATED — " if demonstration else "") + "Lookup-only mappings — DEMONSTRATION ONLY, NOT FOR REDISTRIBUTION"
        lookup_path = directory / "lookup-only.sssom.tsv"
        write_sssom(lookup_path, {"mapping_set_id": app.cfg["exports"]["mapping_set_id"] + "/lookup-only", "mapping_set_version": version,
            "mapping_set_title": lookup_title, "mapping_set_description": lookup_title + "; targets (" + resources + ") came from a public lookup service, "
            "not a licensed release, and are not covered by the CC BY licence of the main mapping set.",
            "license": LOOKUP_ONLY_LICENSE, "curie_map": curies, "mapping_tool": "farajamh", "mapping_tool_version": __version__}, lookup_rows)
        lookup_validation = validate_sssom(lookup_path)
    title = "SIMULATED — NOT FOR RELEASE" if demonstration else "Human-reviewed synthetic research mappings"
    if include_lookup and lookup_rows:
        title += " — TEST: includes lookup-only SNOMED CT rows, not for redistribution"
    metadata = {"mapping_set_id": app.cfg["exports"]["mapping_set_id"] + ("/SIMULATED" if demonstration else ""),
        "mapping_set_version": version, "mapping_set_title": title, "mapping_set_description": title + "; details in mapping-provenance.json",
        "license": app.cfg["exports"]["license"], "curie_map": curies,
        "mapping_tool": "farajamh", "mapping_tool_version": __version__}
    path = directory / ("SIMULATED.mappings.sssom.tsv" if demonstration else "mappings.sssom.tsv")
    write_sssom(path, metadata, rows)
    validation = validate_sssom(path)
    write_json(directory / "mapping-provenance.json", sidecar)
    write_json(directory / "excluded-mappings.json", excluded)
    write_json(directory / "excluded-cases.json", excluded_cases)
    write_json(directory / "contextual-assertions.json", assertions)
    write_json(directory / "ckb.json", [s for s in senses.values() if app.sense_current(s) and (demonstration or not s["simulated"])])
    write_json(directory / "unresolved-and-gaps.json", [{"utterance_id": d["source"]["utterance_id"], "state": d["state"],
        "mapping_reviews": [m for m in d["mapping_reviews"] if m["decision"]["action"] != "approve"]} for d in dossiers])
    write_csv(directory / "approved-synthetic.csv", approved_sources, ["utterance_id", "original_text", "synthetic"])
    write_csv(directory / "approved-mappings.csv", rows, FIELDS)
    write_csv(directory / "local-concepts.csv", list(concepts.values()), CONCEPT_FIELDS)
    catalog(directory, ["approved-synthetic.csv", "approved-mappings.csv", "local-concepts.csv", path.name], demonstration, app.cfg, version)
    with app.store.transaction():
        app.store.event(person["id"], "DEMONSTRATION_EXPORT" if demonstration else "RELEASE_EXPORT", str(directory),
            {"mapping_rows": len(rows), "mapping_set_version": version, "content_digest": digest([sidecar, excluded]), "excluded_mappings": excluded, "lookup_only_rows": len(lookup_rows), "excluded_cases": excluded_cases, "versions": {d["source"]["utterance_id"]: d["version"] for d in dossiers}, "validation": validation})
    return {"path": str(path), "rows": len(rows), "excluded_mappings": len(excluded), "lookup_only_rows": len(lookup_rows), "lookup_only_included": include_lookup, "lookup_only_validation": lookup_validation and "SSSOM 1.0 profile passed", "excluded_cases": len(excluded_cases), "exclusion_report": str(directory / "excluded-mappings.json"), "demonstration": demonstration, "validation": "SSSOM 1.0 profile and local Croissant profile passed"}


LOOKUP_ONLY_LICENSE = "https://www.snomed.org/get-snomed"


def write_sssom(path: Path, metadata: dict, rows: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as stream:
        for line in yaml.safe_dump(metadata, sort_keys=False).splitlines():
            stream.write("# " + line + "\n")
        writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows({k: str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ") for k, v in row.items()} for row in rows)


def catalog(directory: Path, files: list[str], demonstration: bool, cfg: dict, version: str):
    distributions, records = [], []
    for filename in files:
        file = directory / filename
        identifier = "file/" + filename
        distributions.append({"@type": "cr:FileObject", "@id": identifier, "name": filename,
            "contentUrl": filename, "encodingFormat": "text/csv" if file.suffix == ".csv" else "text/tab-separated-values", "sha256": file_hash(file)})
        if file.suffix == ".csv":
            with file.open() as stream:
                fields = next(csv.reader(stream))
            records.append({"@type": "cr:RecordSet", "@id": "records/" + filename, "name": filename.removesuffix(".csv"),
                "description": "Synthetic approved workflow artifact; simulated reviews explicitly labelled",
                "field": [{"@type": "cr:Field", "@id": "records/" + filename + "/" + name, "name": name,
                    "description": FIELD_DESCRIPTIONS.get(name, name.replace("_", " ")), "dataType": "sc:Text",
                    "source": {"fileObject": {"@id": identifier}, "extract": {"column": name}}} for name in fields]})
    context = json.loads((ROOT / "schemas/croissant-context-1.0.json").read_text())
    # Identified under the mapping-set URI, never by a local file path.
    data = {"@context": context, "@type": "sc:Dataset", "@id": cfg["exports"]["mapping_set_id"] + "/" + directory.name,
        "name": "FarajaMH synthetic workflow — " + ("SIMULATED NOT FOR RELEASE" if demonstration else "human-reviewed"),
        "description": "Synthetic research artifacts. Catalog metadata does not establish clinical or cultural validity." + (
            " Test package: mappings include lookup-only SNOMED CT rows from a public lookup service; not for redistribution." if cfg["exports"].get("include_lookup_only") else ""),
        "citeAs": "FarajaMH synthetic software demonstration, prototype 1.0.0; not a validated research dataset.",
        "creator": {"@type": "sc:Organization", "name": cfg["exports"].get("creator", "FarajaMH Minority Report project")},
        "license": cfg["exports"]["license"], "version": version, "datePublished": now()[:10],
        "conformsTo": "http://mlcommons.org/croissant/1.0", "distribution": distributions, "recordSet": records}
    write_json(directory / "catalog.jsonld", data)
    return validate_catalog(directory / "catalog.jsonld")


def validate_catalog(path: Path) -> dict:
    data = json.loads(path.read_text())
    require(isinstance(data.get("@context"), dict), "Only local inline JSON-LD context permitted")
    require(data.get("conformsTo") == "http://mlcommons.org/croissant/1.0" and data.get("recordSet"), "Croissant 1.0 recordsets required")
    Graph().parse(data=canonical(data), format="json-ld")  # RDF validity with no network context resolution
    files = {}
    for distribution in data["distribution"]:
        require(distribution["@type"] == "cr:FileObject", "Expected FileObject")
        parsed = urlparse(distribution["contentUrl"])
        require(parsed.scheme in ("", "file"), "Local catalog must reference local artifacts")
        file = Path(unquote(parsed.path)) if parsed.scheme else path.parent / unquote(parsed.path)
        require(file.resolve().is_relative_to(path.parent.resolve()), "Artifact must be inside the export directory")
        require(file.is_file() and file_hash(file) == distribution["sha256"], "Unresolvable artifact or checksum mismatch")
        files[distribution["@id"]] = file
    for record in data["recordSet"]:
        for field in record["field"]:
            source = field["source"]
            require(source["fileObject"]["@id"] in files, "Unknown FileObject")
            with files[source["fileObject"]["@id"]].open() as stream:
                require(source["extract"]["column"] in next(csv.reader(stream)), "Unknown CSV field")
    return {"validator": "farajamh-croissant-1.0-profile/1.0.0", "files": len(files), "jsonld": "valid"}
