#!/usr/bin/env python3
"""Apply approved TP-fix replacements to transcripts. Input: JSON with first-occurrence-only replacement."""

import argparse
import json
import sys
from pathlib import Path

from tools import printer


def apply_fixes(fix_list: list[dict]) -> tuple[int, int]:
    applied = 0
    skipped = 0

    for entry in fix_list:
        file_path_str = entry.get("file", "")
        replacements = entry.get("replacements", [])

        if not file_path_str or not replacements:
            skipped += 1
            continue

        path = Path(file_path_str)
        if not path.exists():
            printer.printer.amber(f"File not found: {file_path_str}")
            skipped += 1
            continue

        content = path.read_text(encoding="utf-8")
        file_applied = 0

        for replacement in replacements:
            old = replacement.get("old", "")
            new = replacement.get("new", "")

            if not old:
                continue

            count = content.count(old)
            if count == 0:
                printer.printer.amber(
                    f"Not found in {file_path_str}: {old[:60]}..."
                    if len(old) > 60
                    else f"Not found in {file_path_str}: {old}"
                )
                continue
            if count > 1:
                printer.printer.amber(
                    f"Ambiguous ({count} occurrences) in {file_path_str}: {old[:60]}..."
                    if len(old) > 60
                    else f"Ambiguous ({count} occurrences) in {file_path_str}: {old}"
                )
                continue

            content = content.replace(old, new, 1)
            file_applied += 1

        if file_applied > 0:
            path.write_text(content, encoding="utf-8")
            applied += file_applied

    return applied, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply TP-fix replacements to transcripts."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("json_file", nargs="?", help="Path to JSON fix file.")
    input_group.add_argument(
        "--stdin", action="store_true", help="Read JSON from stdin."
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.stdin:
        raw = sys.stdin.read()
    else:
        raw = Path(args.json_file).read_text(encoding="utf-8")

    try:
        fix_list = json.loads(raw)
    except json.JSONDecodeError as exc:
        pr = printer.printer
        pr.no(f"Invalid JSON: {exc}")
        return 1

    if not isinstance(fix_list, list):
        pr = printer.printer
        pr.no("JSON must be a list of fix entries.")
        return 1

    for entry in fix_list:
        if not isinstance(entry, dict):
            pr = printer.printer
            pr.no("Each fix entry must be an object.")
            return 1
        if "file" not in entry:
            pr = printer.printer
            pr.no("Each fix entry must have a 'file' key.")
            return 1
        replacements = entry.get("replacements", [])
        if not isinstance(replacements, list):
            pr = printer.printer
            pr.no("'replacements' must be a list.")
            return 1
        for r in replacements:
            if not isinstance(r, dict):
                pr = printer.printer
                pr.no("Each replacement must be an object with 'old' and 'new' keys.")
                return 1
            if "old" not in r or "new" not in r:
                pr = printer.printer
                pr.no("Each replacement must have 'old' and 'new' keys.")
                return 1

    applied, skipped = apply_fixes(fix_list)

    pr = printer.printer
    pr.yes(f"Fixes applied: {applied}, entries skipped: {skipped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
