"""Two-way sync between the master workshop workbook and the review app's dictionary JSON.

The team keeps the dictionary in the master workbook ("Dummy dictionary" sheet). At the start of every new
expression the app:
  1. adds, as "System proposal" rows, reviewed local concepts that are not in the workbook yet; and
  2. rebuilds the dictionary JSON from the workbook when the workbook has changed.

A local concept becomes a proposal only when it is the latest version, approved for reuse, still matches its
meaning decision, is not simulated, its case is not flagged test/withdrawn, and its expression is not already
in the workbook. The app only ever adds rows; it never changes Status, meaning or From case typed by the team.
Every write is preceded by a dated backup and skipped while Excel has the workbook open. A row the team
deletes is added again on the next sync, so reject a row (Status: Rejected) rather than deleting it.
"""
import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from contextlib import contextmanager
from copy import copy
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

from .common import CATEGORY_FAMILIES, resolve

SHEET = "Dummy dictionary"
COLUMNS = {"Entry ID": "id", "Expression": "expression", "Invented meaning": "meaning", "Family": "family",
           "Workbook code": "category_code", "Context limits (invented)": "context_limits", "Wording source": "source",
           "Approval status": "approval_status", "Workshop DAP category": "workshop_dap",
           "Origin": "origin", "Status": "status", "From case": "from_case"}
ORIGINS = {"Workshop Proposal", "Test wording", "System proposal"}
STATUSES = {"Proposed", "Validated", "Rejected"}
BACKUPS_KEPT = 30
_thread_lock = threading.Lock()


class SyncError(ValueError):
    pass


def normal(text):
    return " ".join(re.findall(r"\w+", str(text or "").casefold()))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _header(rows):
    for index, row in enumerate(rows):
        if row and row[0] == "Entry ID":
            return index
    raise SyncError(f"{SHEET} sheet has no 'Entry ID' header row")


def read_workbook(path):
    """Entries from the master workbook. Raises SyncError listing every row to fix."""
    try:
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise SyncError(f"Workbook could not be read ({type(exc).__name__}); is it half-saved or not an .xlsx?") from exc
    if SHEET not in book.sheetnames:
        raise SyncError(f"Workbook has no '{SHEET}' sheet")
    rows = list(book[SHEET].iter_rows(values_only=True))
    header = _header(rows)
    names = [COLUMNS.get(str(c).strip()) if c else None for c in rows[header]]
    missing = [title for title, key in COLUMNS.items() if key not in names]
    if missing:
        raise SyncError(f"{SHEET} sheet is missing columns: {missing}")
    entries, problems = [], []
    for row in rows[header + 1:]:
        if not (row and isinstance(row[0], str) and row[0].strip()):
            continue
        cell = {n: (v.strip() if isinstance(v, str) else v) for n, v in zip(names, row) if n}
        if cell["approval_status"] != "SIMULATED_NOT_APPROVED":
            problems.append(f"{cell['id']}: Approval status must be SIMULATED_NOT_APPROVED in the dummy dictionary")
        if cell["origin"] not in ORIGINS:
            problems.append(f"{cell['id']}: Origin must be one of {sorted(ORIGINS)}, not {cell['origin']!r}")
        if cell["status"] not in STATUSES:
            problems.append(f"{cell['id']}: Status must be one of {sorted(STATUSES)}, not {cell['status']!r}")
        if not cell["from_case"]:
            problems.append(f"{cell['id']}: From case is empty (workshop town or case ID)")
        entries.append({"id": cell["id"], "expression": cell["expression"], "meaning": cell["meaning"],
                        "family": cell["family"], "category_code": cell["category_code"], "context_limits": cell["context_limits"],
                        "source": cell["source"], "workshop_dap": cell["workshop_dap"], "origin": cell["origin"],
                        "status": cell["status"], "from_case": cell["from_case"], "synthetic": True,
                        "approval_status": cell["approval_status"], "external_mapping": None})
    ids = [e["id"] for e in entries]
    problems += [f"{i}: duplicate Entry ID" for i in sorted({i for i in ids if ids.count(i) > 1})]
    if problems:
        raise SyncError("Workbook rows to fix: " + "; ".join(problems))
    return entries


def proposals(app):
    """Reviewed local concepts that qualify as System proposal rows (whether or not already in the workbook)."""
    from .pipeline import excluded_case
    latest = {}
    for sense in app.store.senses():
        if sense["id"] not in latest or sense["version"] > latest[sense["id"]]["version"]:
            latest[sense["id"]] = sense
    rows = []
    for sense in sorted(latest.values(), key=lambda s: (s["origin_utterance"], s["id"])):
        if not sense.get("reuse_approved") or sense.get("simulated") or not app.sense_current(sense):
            continue
        case = app.store.get(sense["origin_utterance"])
        if excluded_case(case) or case.get("mode") == "fixture":
            continue
        notes = sense.get("review_annotations") or {}
        code = notes.get("family_code") or "undetermined"
        family = CATEGORY_FAMILIES.get(code, [code.replace("_", " ")])[0]
        uid, n = sense["origin_utterance"], (re.search(r"-(\d+)$", sense["id"]) or [None, "1"])[1]  # meaning number in the concept ID
        rows.append({"Entry ID": f"SYSTEM_{uid}" + ("" if n == "1" else f"_{n}"),
                     "Expression": sense["source_label"].strip(),
                     "Invented meaning": (sense.get("meaning") or {}).get("meaning") or sense.get("english_gloss"),
                     "Family": family, "Workbook code": code,
                     "Context limits (invented)": sense.get("cultural_applicability"),
                     "Wording source": f"Reviewed in the app: concept {sense['id']} v{sense['version']}, by {sense['curator']['id']} on {sense['created_at'][:10]}",
                     "Approval status": "SIMULATED_NOT_APPROVED",
                     "Workshop DAP category": ", ".join(notes.get("dap_categories") or []) or "Not recorded",
                     "Origin": "System proposal", "Status": "Proposed", "From case": uid})
    return rows


def missing_proposals(app, entries):
    known_ids = {e["id"] for e in entries}
    known_expressions = {normal(e["expression"]) for e in entries}
    out, seen = [], set()
    for row in proposals(app):
        key = normal(row["Expression"])
        if row["Entry ID"] in known_ids or key in known_expressions or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def excel_open(path):
    path = Path(path)
    return (path.parent / ("~$" + path.name)).exists()


def append_rows(path, rows, backup_dir):
    """Backup, then append rows to the sheet with the last data row's styling; atomic replace."""
    path = Path(path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    shutil.copy2(path, backup_dir / f"{path.stem}-{stamp}{path.suffix}")
    for old in sorted(backup_dir.glob(f"{path.stem}-*{path.suffix}"))[:-BACKUPS_KEPT]:
        old.unlink()
    book = openpyxl.load_workbook(path)
    sheet = book[SHEET]
    header = next(r for r in range(1, sheet.max_row + 1) if sheet.cell(r, 1).value == "Entry ID")
    columns = {sheet.cell(header, c).value: c for c in range(1, sheet.max_column + 1) if sheet.cell(header, c).value}
    last = max(r for r in range(header, sheet.max_row + 1) if sheet.cell(r, 1).value)
    for offset, row in enumerate(rows, start=1):
        for title, value in row.items():
            cell = sheet.cell(last + offset, columns[title], value)
            cell._style = copy(sheet.cell(last, columns[title])._style)
    handle, temp = tempfile.mkstemp(prefix="~$sync-", suffix=path.suffix, dir=path.parent)
    os.close(handle)
    try:
        book.save(temp)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, entries, workbook, workbook_sha):
    version = "master-" + workbook_sha[:10]
    body = {"version": version, "synthetic": True, "curator_approved": False, "source_workbook": Path(workbook).name,
            "source_sha256": workbook_sha, "synced_at": datetime.now(timezone.utc).isoformat(),
            "entries": [{**e, "version": version} for e in entries]}
    handle, temp = tempfile.mkstemp(prefix=".dictionary-", suffix=".json", dir=Path(path).parent)
    with os.fdopen(handle, "w") as out:
        out.write(json.dumps(body, ensure_ascii=False, indent=2) + "\n")
    os.replace(temp, path)
    return version


@contextmanager
def _locked(cfg):
    lock_path = resolve(cfg, cfg["storage"]).parent / "dictionary-sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock, open(lock_path, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def sync(cfg, app=None, write=True):
    """Sync before a new expression. Returns a report, or None when no master workbook is configured.

    Never raises for workbook problems: the last good dictionary stays in use and the report says why.
    """
    settings = cfg.get("dictionary") or {}
    if not settings.get("workbook") or not settings.get("path"):
        return None
    workbook, target = resolve(cfg, settings["workbook"]), resolve(cfg, settings["path"])
    backup_dir = resolve(cfg, settings.get("workbook_backups", str(Path(cfg["storage"]).parent / "workbook-backups")))
    report = {"state": "UNCHANGED", "workbook": workbook.name, "proposals_added": [], "warnings": []}
    with _locked(cfg):
        if not workbook.exists():
            report.update(state="WARNING", warnings=[f"Master workbook not found: {workbook.name}; using the last dictionary"])
            return report
        try:
            entries = read_workbook(workbook)
        except SyncError as exc:
            report.update(state="WARNING", warnings=[str(exc) + "; using the last dictionary"])
            return report
        new = missing_proposals(app, entries) if app else []
        report["proposals_pending"] = [r["Entry ID"] for r in new]
        if new and write:
            if excel_open(workbook):
                report["warnings"].append(f"{len(new)} system proposal(s) not written: the workbook is open in Excel. They will be added at the next sync.")
            else:
                append_rows(workbook, new, backup_dir)
                report["proposals_added"] = [f"{r['Entry ID']} ({r['Expression']})" for r in new]
                entries = read_workbook(workbook)
        workbook_sha = sha256(workbook)
        current = json.loads(target.read_text()) if target.exists() else {}
        if current.get("source_sha256") != workbook_sha:
            old = {e["id"] for e in current.get("entries", [])}
            report["entries_added"] = [e["id"] for e in entries if e["id"] not in old]
            if write:
                report["version"] = write_json(target, entries, workbook, workbook_sha)
            report["state"] = "UPDATED"
        else:
            report["version"] = current.get("version")
        if report["warnings"]:
            report["state"] = "WARNING" if report["state"] == "UNCHANGED" else report["state"]
        report["entries"] = len(entries)
    return report


def summary(report):
    """One line for the run log."""
    parts = []
    if report.get("entries_added"):
        parts.append(f"{len(report['entries_added'])} new workbook entries")
    if report["proposals_added"]:
        parts.append("system proposals added: " + ", ".join(report["proposals_added"]))
    if report["state"] == "UPDATED" and not parts:
        parts.append("workbook edits picked up")
    parts += report["warnings"]
    return f"{report['workbook']}: " + ("; ".join(parts) if parts else f"up to date ({report.get('entries', 0)} entries)")
