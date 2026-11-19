import json
import shutil

import openpyxl
import pytest

from conftest import ROOT, curated
from farajamh import workshop_dictionary as wd
from farajamh.dictionary import evidence

MASTER = ROOT / "outputs/workshop-dummy/FarajaMH_Workshop_master_Pack.xlsx"


@pytest.fixture
def master(cfg, tmp_path):
    """Copies of the master workbook and dictionary JSON, wired into the test config."""
    book, target = tmp_path / "book" / MASTER.name, tmp_path / "book" / "dictionary.json"
    book.parent.mkdir()
    shutil.copy(MASTER, book)
    shutil.copy(ROOT / "pilot/workshop-dummy/dictionary.json", target)
    cfg["dictionary"] = {"path": str(target), "workbook": str(book)}
    return book, target


def real_case(app, monkeypatch, sense_changes=None):
    """Fixture cases are simulated and never proposed; treat this one as a real, connected-mode review."""
    if getattr(app, "last_workbook_sync", None):
        app.last_workbook_sync.join()  # the save's own background sync (which sees a simulated case) finishes first
    original = app.store.get
    monkeypatch.setattr(app.store, "get", lambda uid: {**original(uid), "mode": "connected"})
    senses = app.store.senses
    monkeypatch.setattr(app.store, "senses", lambda: [{**s, "simulated": False, **(sense_changes or {})} for s in senses()])


def sheet_rows(book):
    rows = list(openpyxl.load_workbook(book, read_only=True)[wd.SHEET].iter_rows(values_only=True))
    header = wd._header(rows)
    return [dict(zip(rows[header], r)) for r in rows[header + 1:] if r[0]]


def test_reviewed_new_expression_is_written_back_as_system_proposal(app, sources, master, monkeypatch, tmp_path):
    book, target = master
    curated(app, sources[0])
    real_case(app, monkeypatch)
    report = wd.sync(app.cfg, app)
    uid = sources[0]["utterance_id"]
    assert report["state"] == "UPDATED" and report["proposals_added"] == [f"SYSTEM_{uid} ({sources[0]['original_text']})"]
    row = sheet_rows(book)[-1]
    assert (row["Origin"], row["Status"], row["From case"], row["Expression"]) == ("System proposal", "Proposed", uid, sources[0]["original_text"])
    assert row["Wording source"].startswith("Reviewed in the app: concept FARAJA:test")
    # A dated backup was taken before writing, and the JSON was rebuilt from the workbook.
    assert len(list((tmp_path / "workbook-backups").glob("*.xlsx"))) == 1
    library = json.loads(target.read_text())
    assert library["source_sha256"] == wd.sha256(book) and library["version"].startswith("master-")
    found = evidence(app.cfg, {"original_text": sources[0]["original_text"]})
    exact = [e for e in found["entries"] if e["match_type"] == "exact expression"]
    assert [(e["origin"], e["from_case"]) for e in exact] == [("System proposal", uid)]
    # Nothing new: the next sync neither writes nor backs up again.
    assert wd.sync(app.cfg, app)["state"] == "UNCHANGED"
    assert len(list((tmp_path / "workbook-backups").glob("*.xlsx"))) == 1


def test_team_edits_are_read_back_and_rejected_rows_stay_rejected(app, sources, master, monkeypatch):
    book, target = master
    curated(app, sources[0])
    real_case(app, monkeypatch)
    wd.sync(app.cfg, app)
    workbook = openpyxl.load_workbook(book)
    sheet = workbook[wd.SHEET]
    header = next(r for r in range(1, sheet.max_row + 1) if sheet.cell(r, 1).value == "Entry ID")
    status_col = [c.value for c in sheet[header]].index("Status") + 1
    last = max(r for r in range(header, sheet.max_row + 1) if sheet.cell(r, 1).value)
    sheet.cell(last, status_col, "Rejected")
    workbook.save(book)
    report = wd.sync(app.cfg, app)
    assert report["state"] == "UPDATED" and not report["proposals_added"]
    assert sheet_rows(book)[-1]["Status"] == "Rejected"
    assert not any(e["origin"] == "System proposal" for e in evidence(app.cfg, {"original_text": sources[0]["original_text"]})["entries"])


def test_open_workbook_is_not_written(app, sources, master, monkeypatch):
    book, _ = master
    curated(app, sources[0])
    real_case(app, monkeypatch)
    (book.parent / ("~$" + book.name)).write_text("excel lock")
    before = wd.sha256(book)
    report = wd.sync(app.cfg, app)
    assert wd.sha256(book) == before and not report["proposals_added"]
    assert "open in Excel" in report["warnings"][0]


def test_broken_workbook_keeps_the_last_dictionary(app, master):
    book, target = master
    workbook = openpyxl.load_workbook(book)
    sheet = workbook[wd.SHEET]
    header = next(r for r in range(1, sheet.max_row + 1) if sheet.cell(r, 1).value == "Entry ID")
    sheet.cell(header + 1, [c.value for c in sheet[header]].index("Origin") + 1, "Somewhere")
    workbook.save(book)
    before = target.read_text()
    report = wd.sync(app.cfg, app)
    assert report["state"] == "WARNING" and "Origin must be one of" in report["warnings"][0]
    assert target.read_text() == before


@pytest.mark.parametrize("changes,flag", [({"reuse_approved": False}, None), ({}, "test"), ({}, "withdrawn")])
def test_only_reusable_active_concepts_are_proposed(app, sources, master, monkeypatch, changes, flag):
    d, _ = curated(app, sources[0])
    if flag:
        d = app.flag_case(sources[0]["utterance_id"], {"status": flag, "reason": "Early trial"}, "token-demo_ke", d["version"])
    real_case(app, monkeypatch, changes)
    assert wd.sync(app.cfg, app)["proposals_added"] == []


def test_simulated_fixture_concepts_are_never_proposed(app, sources, master):
    curated(app, sources[0])
    assert wd.sync(app.cfg, app)["proposals_added"] == []


def test_run_syncs_before_the_dictionary_check(app, sources, master):
    events = []
    app.run(sources[0], progress=events.append)
    stages = [e["stage"] for e in events]
    assert stages.index("dictionary_sync") == stages.index("dictionary") - 1
    assert next(e for e in events if e["stage"] == "dictionary_sync")["reason"].startswith(MASTER.name)


def set_status(book, entry_id, status):
    workbook = openpyxl.load_workbook(book)
    sheet = workbook[wd.SHEET]
    header = next(r for r in range(1, sheet.max_row + 1) if sheet.cell(r, 1).value == "Entry ID")
    column = [c.value for c in sheet[header]].index("Status") + 1
    row = next(r for r in range(header, sheet.max_row + 1) if sheet.cell(r, 1).value == entry_id)
    sheet.cell(row, column, status)
    workbook.save(book)


def test_unticking_reuse_removes_a_proposed_row(app, sources, master, monkeypatch, tmp_path):
    book, target = master
    curated(app, sources[0])
    real_case(app, monkeypatch)
    wd.sync(app.cfg, app)
    uid = sources[0]["utterance_id"]
    assert sheet_rows(book)[-1]["Entry ID"] == f"SYSTEM_{uid}"
    real_case(app, monkeypatch, {"reuse_approved": False})
    report = wd.sync(app.cfg, app)
    assert report["proposals_removed"] == [f"SYSTEM_{uid} ({sources[0]['original_text']}: no longer approved for reuse)"]
    assert f"SYSTEM_{uid}" not in [r["Entry ID"] for r in sheet_rows(book)]
    assert not any(e["id"] == f"SYSTEM_{uid}" for e in json.loads(target.read_text())["entries"])
    assert len(list((tmp_path / "workbook-backups").glob("*.xlsx"))) == 2  # one backup per write
    # Ticking it again brings the proposal back.
    real_case(app, monkeypatch, {"reuse_approved": True})
    assert wd.sync(app.cfg, app)["proposals_added"]


@pytest.mark.parametrize("status", ["Validated", "Rejected"])
def test_rows_the_team_has_decided_stay(app, sources, master, monkeypatch, status):
    book, _ = master
    curated(app, sources[0])
    real_case(app, monkeypatch)
    wd.sync(app.cfg, app)
    uid = sources[0]["utterance_id"]
    set_status(book, f"SYSTEM_{uid}", status)
    real_case(app, monkeypatch, {"reuse_approved": False})
    report = wd.sync(app.cfg, app)
    assert not report["proposals_removed"] and f"Status is {status}" in report["left_in_place"][0]
    assert sheet_rows(book)[-1]["Status"] == status


def test_rows_from_another_database_are_never_removed(app, sources, master, monkeypatch):
    # A System proposal row whose case is not in this database is left alone.
    book, _ = master
    curated(app, sources[0])
    real_case(app, monkeypatch)
    wd.sync(app.cfg, app)
    other = wd.review_rows(app)[0][0] | {"Entry ID": "SYSTEM_ELSEWHERE-1", "Expression": "elsewhere words", "From case": "ELSEWHERE-1"}
    wd.edit_rows(book, [other], [], book.parent / "bk")
    real_case(app, monkeypatch, {"reuse_approved": False})
    wd.sync(app.cfg, app)
    assert "SYSTEM_ELSEWHERE-1" in [r["Entry ID"] for r in sheet_rows(book)]


def test_saving_a_concept_starts_a_background_sync(app, sources, master):
    curated(app, sources[0])
    assert app.last_workbook_sync is not None
    app.last_workbook_sync.join(timeout=30)
    assert not app.last_workbook_sync.is_alive()


def test_no_background_sync_without_a_workbook(app, sources):
    curated(app, sources[0])
    assert app.last_workbook_sync is None
