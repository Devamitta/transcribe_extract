#!/usr/bin/env python3
"""Unreviewed semantic-report queue: mtime vs ledger, NFC normalization, SESSION_LIMIT=10."""

import argparse
import json
import sys
import unicodedata
from pathlib import Path

from tools import printer


SESSION_LIMIT = 10


def resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _nfc(name: str) -> str:
    return unicodedata.normalize("NFC", name)


def load_ledger_mtimes(ledger_path: Path) -> dict[str, float]:
    if not ledger_path.exists():
        return {}
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    entries = ledger.get("processed_files", [])
    result: dict[str, float] = {}
    for entry in entries:
        if isinstance(entry, dict):
            filename = entry.get("file", entry.get("filename", ""))
            mtime = entry.get("mtime", 0)
            if filename:
                result[_nfc(filename)] = float(mtime)
    return result


def build_report_list(
    reports_dir: Path, ledger_mtimes: dict[str, float]
) -> tuple[list[dict], int]:
    all_reports: list[dict] = []
    unreviewed: list[dict] = []

    if not reports_dir.exists() or not reports_dir.is_dir():
        return [], 0

    for f in sorted(reports_dir.glob("*.md")):
        if not f.is_file():
            continue
        report_mtime = f.stat().st_mtime
        filename_nfc = _nfc(f.name)
        ledger_mtime = ledger_mtimes.get(filename_nfc, 0)
        all_reports.append(
            {
                "filename": f.name,
                "path": str(f),
                "mtime": report_mtime,
                "reviewed": report_mtime <= ledger_mtime,
            }
        )

    unreviewed = [r for r in all_reports if not r["reviewed"]]
    total_on_disk = len(all_reports)

    return unreviewed, total_on_disk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build unreviewed semantic-report queue."
    )
    parser.add_argument(
        "--folder", default="interview", help="Pipeline folder (default: interview)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root path (default: auto-detected from script location).",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = args.root or resolve_repo_root()

    reports_dir = root / "reports" / "semantic" / args.folder
    ledger_path = root / "kamma" / "enhance" / "data" / "semantic-ledger.json"

    ledger_mtimes = load_ledger_mtimes(ledger_path)
    unreviewed, total_on_disk = build_report_list(reports_dir, ledger_mtimes)

    limited = unreviewed[:SESSION_LIMIT]
    pending_count = max(0, len(unreviewed) - SESSION_LIMIT)

    result = {
        "reports": [
            {
                "path": r["path"],
                "filename": r["filename"],
            }
            for r in limited
        ],
        "pending_count": pending_count,
        "total_on_disk": total_on_disk,
    }

    pr = printer.printer
    pr.green(f"Folder:          {args.folder}")
    pr.green(f"Total on disk:   {total_on_disk}")
    pr.green(f"Unreviewed:      {len(unreviewed)}")
    pr.green(f"Session reports: {len(limited)}")
    pr.green(f"Pending:         {pending_count}")
    print()
    print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
