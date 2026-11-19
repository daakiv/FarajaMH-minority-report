"""Sync the master workshop workbook and the review app's dictionary now, outside a run.

The app already does this at the start of every new expression (farajamh/workshop_dictionary.py). Use this
after editing the workbook, or with --check to preview what a sync would add without writing anything.

    .venv/bin/python tools/sync_workshop_dictionary.py [--config config.live-test.yaml] [--check]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farajamh import workshop_dictionary  # noqa: E402
from farajamh.common import config  # noqa: E402
from farajamh.pipeline import App  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Sync the master workshop workbook and the dictionary JSON.")
    parser.add_argument("--config", default="config.live-test.yaml")
    parser.add_argument("--check", action="store_true", help="Preview only: write neither the workbook nor the JSON")
    args = parser.parse_args()
    cfg = config(Path(args.config))
    app = App(cfg)
    try:
        report = workshop_dictionary.sync(cfg, app, write=not args.check)
    finally:
        app.store.db.close()
    if report is None:
        raise SystemExit("No dictionary.workbook in this config; nothing to sync.")
    if args.check:
        print(f"Preview ({report['workbook']}, {report['entries']} entries in workbook):")
        print("  System proposals that would be added:", report.get("proposals_pending") or "none")
        print("  Workbook changed since the last sync:", "yes" if report["state"] == "UPDATED" else "no")
        for warning in report["warnings"]:
            print("  Warning:", warning)
    else:
        print(workshop_dictionary.summary(report))
        if report.get("version"):
            print("Dictionary version:", report["version"])


if __name__ == "__main__":
    main()
