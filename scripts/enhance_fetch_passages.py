#!/usr/bin/env python3
"""Fetch specified line ranges from source files with surrounding context."""

import argparse
import sys
from pathlib import Path

from tools import printer


def parse_range(raw: str) -> tuple[int, int]:
    parts = raw.split(":")
    range_part = parts[1] if len(parts) > 1 else ""

    range_match = (
        range_part.split("-") if "-" in range_part else [range_part, range_part]
    )
    try:
        start = int(range_match[0]) if range_match[0] else 1
        end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else start
    except ValueError:
        start = 1
        end = 1

    return start, end


def merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda x: x[0])
    merged = [sorted_ranges[0]]
    for current in sorted_ranges[1:]:
        last = merged[-1]
        if current[0] <= last[1] + 1:
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)
    return merged


def fetch_passage(
    file_path: Path, start: int, end: int, context_lines: int = 2
) -> str | None:
    if not file_path.exists():
        return None

    lines = file_path.read_text(encoding="utf-8").split("\n")
    num_lines = len(lines)

    ctx_start = max(1, start - context_lines)
    ctx_end = min(num_lines, end + context_lines)

    result_lines: list[str] = []
    for i in range(ctx_start - 1, ctx_end):
        line_num = i + 1
        if start <= line_num <= end:
            result_lines.append(f">>> L{line_num}: {lines[i]}")
        else:
            result_lines.append(f"    L{line_num}: {lines[i]}")

    return "\n".join(result_lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch line ranges from source files with context."
    )
    parser.add_argument(
        "references",
        nargs="+",
        help="File references in format: file.md:start-end (e.g. report.md:10-15)",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=2,
        help="Lines of surrounding context (default: 2).",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    pr = printer.printer

    for raw_ref in args.references:
        start, end = parse_range(raw_ref)
        file_str = raw_ref.split(":")[0]
        file_path = Path(file_str)

        passage = fetch_passage(file_path, start, end, args.context)
        if passage is None:
            pr.amber(f"File not found: {file_path}")
            continue

        pr.green(f"\n=== {file_path}:L{start}-L{end} ===")
        print(passage)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
