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
from .common import ROOT, RESOURCES, canonical, digest, file_hash, now, require, write_json

SEARCH_PROBLEM = {"SEARCH_FAILED": "the search failed; rerun it", "UNAVAILABLE": "the source was unavailable; rerun the search"}
FIELDS = ["subject_id", "object_id", "predicate_id", "mapping_justification", "subject_label", "object_label",
    "author_id", "reviewer_id", "mapping_date", "subject_source_version", "object_source_version", "mapping_tool", "mapping_tool_version"]


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
    require(reader.fieldnames == FIELDS, "Unexpected SSSOM profile slots")
    rows = list(reader)
    for row in rows:
        require(all(row.get(k) for k in FIELDS[:4]), "Required SSSOM fields absent")
        for key in ("subject_id", "object_id", "predicate_id", "mapping_justification", "author_id", "reviewer_id"):
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


def export_readiness(app, dossier, person, demonstration=False):
    """Shared recorded-state blockers; export still verifies live releases and targets."""
    blockers, excluded = [], []
    flag = (dossier.get("case_flag") or {}).get("status")
    if flag in ("test", "withdrawn"):
        return {"status": "EXCLUDED", "blockers": [], "excluded_mappings": [],
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
            excluded.append(exclusion)
            continue
        sense = senses.get(mapping["decision"]["sense_id"])
        if not sense or not app.sense_current(sense) or sense["version"] != mapping["sense_version"]:
            blockers.append("Curated sense changed: mapping stale")
        if mapping.get("meaning_decision_hash") != (dossier.get("adjudication") or {}).get("decision_hash"):
            blockers.append("Meaning changed: mapping stale")
        if not demonstration and (mapping["identity"].get("simulated") or (sense or {}).get("simulated") or mapping.get("candidate", {}).get("fixture")):
            blockers.append("Simulated curation or fictional candidates cannot be released")
    return {"status": "BLOCKED" if blockers else "READY_FOR_FINAL_CHECK", "blockers": list(dict.fromkeys(blockers)), "excluded_mappings": excluded,
        "notice": "Recorded-state check only. Final export checks every eligible case, current resource releases and active targets. No mapping is required to retain an approved local meaning."}


def export_sssom(app, directory: Path, token: str, demonstration: bool = False) -> dict:
    person = app.identity(token, "terminology")
    app.check_mode()
    require(not directory.exists(), "Output directory exists; export a new immutable snapshot")
    require(not demonstration or app.cfg["mode"] == "fixture", "Demonstration export only in fixture mode")
    if not demonstration:
        require(app.cfg["mode"] != "fixture" and not person["simulated"], "Fixture/simulated approvals cannot produce a research release")
    rows, sidecar, assertions, approved_sources, excluded = [], [], [], [], []
    senses = {s["id"]: s for s in app.store.senses()}
    curies = dict(app.cfg["exports"]["curie_map"])
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
        readiness = export_readiness(app, d, person, demonstration)
        require(not readiness["blockers"], "; ".join(readiness["blockers"]))
        # Every required resource must have been successfully searched; no forced mapping required.
        for resource in RESOURCES:
            lookup = d["terminology"].get(resource, {})
            require(lookup.get("state") in ("HITS", "NO_RESULTS"), f"{resource}: required terminology review incomplete — " + SEARCH_PROBLEM.get(lookup.get("state"), "not searched yet"))
            current = app.resolver.metadata(resource)
            require(digest(current) == digest(lookup["metadata"]), f"{resource}: resource version changed; mappings stale")
        for mapping in d["mapping_reviews"]:
            if mapping["stale"] or mapping["decision"]["action"] != "approve":
                continue
            decision = mapping["decision"]
            exclusion = mapping_exclusion(app, mapping)
            if exclusion:
                excluded.append({**exclusion, "utterance_id": d["source"]["utterance_id"], "dossier_version": d["version"]})
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
                continue
            require(candidate["active"] and candidate["release"] == mapping["candidate"]["release"], "Target inactive or release changed")
            require(demonstration or not candidate["fixture"], "Fictional candidate cannot be released")
            prefix, local = candidate["id"].split(":", 1)
            if prefix not in curies:
                require(candidate["iri"].endswith(local), "Cannot declare CURIE from verified IRI")
                curies[prefix] = candidate["iri"][:-len(local)]
            rows.append({"subject_id": sense["id"], "object_id": candidate["id"], "predicate_id": decision["predicate"],
                "mapping_justification": "semapv:UnspecifiedMatching" if demonstration else "semapv:ManualMappingCuration", "subject_label": sense["english_gloss"],
                "object_label": candidate["label"], "author_id": "reviewer:" + mapping["identity"]["id"],
                "reviewer_id": "reviewer:" + mapping["identity"]["id"], "mapping_date": mapping["timestamp"][:10],
                "subject_source_version": str(sense["version"]), "object_source_version": candidate["release"],
                "mapping_tool": "farajamh", "mapping_tool_version": __version__})
            sidecar.append({"row": len(rows), "utterance_id": d["source"]["utterance_id"], "dossier_version": d["version"],
                "decision": mapping, "demonstration": demonstration, "curation_notice": "SIMULATED manual-curation workflow, not human-reviewed" if demonstration else "Actual human curation"})
        source = d["source"]
        assertions.append({"utterance_id": source["utterance_id"], "source_version": d["version"],
            "synthetic": True, "simulated_review": demonstration, "sense_links": [link for link in d["sense_links"]
                if not link.get("stale") and link["id"] in senses and senses[link["id"]]["version"] == link["version"] and app.sense_current(senses[link["id"]])],
            "qualifiers": source["qualifiers"], "adjudicated_meanings": d["adjudication"]["decision"]["meanings"],
            "risk_review_queue": d["priority"]["queue"], "omop_concept_id": None})
        approved_sources.append({"utterance_id": source["utterance_id"], "original_text": source["original_text"], "synthetic": "true"})
    require(assertions, "No adjudicated eligible records to export")
    directory.mkdir(parents=True)
    title = "SIMULATED — NOT FOR RELEASE" if demonstration else "Human-reviewed synthetic research mappings"
    metadata = {"mapping_set_id": app.cfg["exports"]["mapping_set_id"] + ("/SIMULATED" if demonstration else ""),
        "mapping_set_version": digest([sidecar, excluded]), "mapping_set_title": title, "mapping_set_description": title + "; details in mapping-provenance.json",
        "license": app.cfg["exports"]["license"], "curie_map": curies,
        "mapping_tool": "farajamh", "mapping_tool_version": __version__}
    path = directory / ("SIMULATED.mappings.sssom.tsv" if demonstration else "mappings.sssom.tsv")
    with path.open("w", newline="", encoding="utf-8") as stream:
        for line in yaml.safe_dump(metadata, sort_keys=False).splitlines():
            stream.write("# " + line + "\n")
        writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows({k: str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ") for k, v in row.items()} for row in rows)
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
    catalog(directory, ["approved-synthetic.csv", "approved-mappings.csv", path.name], demonstration)
    with app.store.transaction():
        app.store.event(person["id"], "DEMONSTRATION_EXPORT" if demonstration else "RELEASE_EXPORT", str(directory),
            {"mapping_rows": len(rows), "excluded_mappings": excluded, "excluded_cases": excluded_cases, "versions": {d["source"]["utterance_id"]: d["version"] for d in dossiers}, "validation": validation})
    return {"path": str(path), "rows": len(rows), "excluded_mappings": len(excluded), "excluded_cases": len(excluded_cases), "exclusion_report": str(directory / "excluded-mappings.json"), "demonstration": demonstration, "validation": "SSSOM 1.0 profile and local Croissant profile passed"}


def catalog(directory: Path, files: list[str], demonstration: bool):
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
                    "description": name.replace("_", " "), "dataType": "sc:Text",
                    "source": {"fileObject": {"@id": identifier}, "extract": {"column": name}}} for name in fields]})
    context = json.loads((ROOT / "schemas/croissant-context-1.0.json").read_text())
    data = {"@context": context, "@type": "sc:Dataset", "@id": (directory / "catalog.jsonld").resolve().as_uri(),
        "name": "FarajaMH synthetic workflow — " + ("SIMULATED NOT FOR RELEASE" if demonstration else "human-reviewed"),
        "description": "Synthetic research artifacts. Catalog metadata does not establish clinical or cultural validity.",
        "citeAs": "FarajaMH synthetic software demonstration, prototype 1.0.0; not a validated research dataset.",
        "license": "https://creativecommons.org/licenses/by/4.0/", "version": "1.0", "datePublished": now()[:10],
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
