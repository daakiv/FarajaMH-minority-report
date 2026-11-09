import csv
import io
import json
import threading
import urllib.error
import urllib.request

import pytest

from conftest import ROOT, approved_mapping
from farajamh.exports import export_readiness, export_sssom, review_package, validate_catalog, validate_sssom
from farajamh.pilot import dry_run
from farajamh.webapp import server


def test_sssom_catalog_and_assertion_separation(app, sources, tmp_path):
    approved_mapping(app, sources[0])
    out = tmp_path / "export"
    exported = export_sssom(app, out, "token-demo_curator", True)
    assert exported["rows"] == 1
    assert validate_sssom(out / "SIMULATED.mappings.sssom.tsv")["rows"] == 1
    assert validate_catalog(out / "catalog.jsonld")["files"] == 4
    # Idiom family travels in the standard subject_category slot; DAP only in the joinable concept table.
    row = next(csv.DictReader(io.StringIO("\n".join(l for l in (out / "SIMULATED.mappings.sssom.tsv").read_text().splitlines() if not l.startswith("#"))), delimiter="\t"))
    concept = next(csv.DictReader((out / "local-concepts.csv").open()))
    assert row["subject_category"] and concept["subject_id"] == row["subject_id"] and concept["idiom_family"] == row["subject_category"]
    assert concept["utterance_id"] == "SYN01" and "dap_categories" in concept and "dap_categories" not in row
    # Excel reading copy: same rows, every cell text so release dates stay as written.
    from openpyxl import load_workbook
    book = load_workbook(out / "mappings.xlsx")
    sheet = book["Mappings"]
    header = [c.value for c in sheet[1]]
    version = sheet.cell(2, header.index("object_source_version") + 1)
    assert book.sheetnames == ["Mappings", "Local concepts"] and version.value == row["object_source_version"] and version.data_type == "s"
    assert "mappings.xlsx" not in (out / "catalog.jsonld").read_text()
    # The Record step preview shows the same local-concepts.csv row before exporting.
    preview = export_readiness(app, app.store.get("SYN01"), app.identity("token-demo_curator"), True)["concepts"]
    assert [{k: v for k, v in c.items()} for c in preview] == [dict(concept)]
    assertion = json.loads((out / "contextual-assertions.json").read_text())[0]
    assert assertion["utterance_id"] == "SYN01" and assertion["omop_concept_id"] is None
    text = (out / "SIMULATED.mappings.sssom.tsv").read_text()
    assert "FARAJA:test" in text and "SYN01" not in text
    assert "ManualMappingCuration" not in text and "semapv:UnspecifiedMatching" in text
    (out / "approved-synthetic.csv").write_text("corrupted")
    with pytest.raises(ValueError, match="checksum"): validate_catalog(out / "catalog.jsonld")


def test_unapproved_rows_never_export(app, sources, tmp_path):
    d, h, payload = approved_mapping(app, sources[0])
    payload["action"] = "reject"
    app.mapping("SYN01", payload, "token-demo_curator", d["version"])
    assert export_sssom(app, tmp_path / "export", "token-demo_curator", True)["rows"] == 0


def test_sssom_undeclared_prefix_rejected(app, sources, tmp_path):
    approved_mapping(app, sources[0])
    out = tmp_path / "export"
    export_sssom(app, out, "token-demo_curator", True)
    path = out / "SIMULATED.mappings.sssom.tsv"
    path.write_text(path.read_text().replace("FARAJA:test", "UNDECLARED:test"))
    with pytest.raises(ValueError, match="CURIE"): validate_sssom(path)


def test_review_package_full_dossier_and_spreadsheet(app, sources, tmp_path):
    app.run(sources[0])
    review_package(app, "SYN01", tmp_path, "token-demo_ke")
    assert (tmp_path / "SYN01.review.xlsx").is_file()
    assert len(json.loads((tmp_path / "SYN01.dossier.json").read_text())["models"]) == 4


def test_official_validators_when_installed(app, sources, tmp_path):
    import importlib.util
    if not importlib.util.find_spec("mlcroissant") or not importlib.util.find_spec("sssom_schema"):
        pytest.skip("Install optional pinned validation dependencies")
    from tools.validate_upstream import validate
    approved_mapping(app, sources[0])
    directory = tmp_path / "official"
    export_sssom(app, directory, "token-demo_curator", True)
    result = validate(directory)
    assert result["official_mapping_model_rows"] == 1
    assert result["recordset_counts"]["records/approved-synthetic.csv"] == 1
    assert result["recordset_counts"]["records/local-concepts.csv"] == 1


def test_end_to_end_offline(cfg, tmp_path):
    out = tmp_path / "pilot"
    result = dry_run(cfg, out)
    assert result["utterances"] == 20 and result["model_counts"]["failed"] == 2
    assert result["real_reviewer_metrics"] == "NOT MEASURED"
    expected = json.loads((ROOT / "pilot/expected.json").read_text())
    for uid, state in expected.items():
        d = json.loads((out / "report/dossiers" / (uid + ".json")).read_text())
        assert d["comparison"]["state"] == state
        assert d["adjudication"]["identity"]["simulated"]
    d = json.loads((out / "report/dossiers/SYN01.json").read_text())
    assert d["adjudication"]["decision"]["action"] == "multiple"
    assert len(d["adjudication"]["decision"]["meanings"]) == 2
    assert validate_catalog(out / "SIMULATED-artifacts/catalog.jsonld")


def test_http_auth_persistence_and_host_guard(app, cfg, sources):
    d = app.run(sources[0])
    http = server(cfg, 0)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{http.server_port}"
    try:
        with urllib.request.urlopen(base) as response:
            assert b"FarajaMH" in response.read()
        with pytest.raises(urllib.error.HTTPError): urllib.request.urlopen(base + "/api/queue")
        from conftest import review_payload
        h = d["comparison"]["groups"][0]["hypotheses"][0]["hypothesis"]
        data = json.dumps({"utterance_id": "SYN01", "version": d["version"], "decision": review_payload(h)}).encode()
        headers = {"Authorization": "Bearer token-demo_ke", "Content-Type": "application/json"}
        with urllib.request.urlopen(urllib.request.Request(base + "/api/review", data=data, headers=headers)) as response:
            assert json.load(response)["version"] == 2
        assert len(app.store.get("SYN01")["reviews"]) == 1
        invalid = {"utterance_id":"SYN01", "version":2, "decision":{**review_payload(h), "comment":42}}
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(base + "/api/review", data=json.dumps(invalid).encode(), headers=headers))
        failure = json.load(error.value)
        assert failure["field"] == "comment" and "comment" in failure["error"]
        assert app.store.get("SYN01")["version"] == 2
        headers["Origin"] = "http://attacker.example"
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(urllib.request.Request(base + "/api/review", data=data, headers=headers))
    finally:
        http.shutdown()
        http.server_close()
        thread.join()
