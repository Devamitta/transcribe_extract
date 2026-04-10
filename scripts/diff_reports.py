#!/usr/bin/env python3
"""Compares two Whisper error reports and summarizes resolved vs. new anomalies."""

import re
import sys
from pathlib import Path
from typing import Dict, Set


def parse_report(file_path: Path) -> Dict[str, Set[str]]:
    """Parses a report into a mapping of filename to set of (anomaly_type, error_block)."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    files = {}
    # Split by file headers
    file_sections = re.split(r"## File: ", content)[1:]

    for section in file_sections:
        lines = section.split("\n")
        filename = lines[0].strip()
        anomalies = set()

        # Find all anomaly blocks
        anomaly_blocks = re.split(r"### Anomaly \d+: ", section)[1:]
        for block in anomaly_blocks:
            lines = block.split("\n")
            anomaly_type = lines[0].strip()

            # Extract the ERROR BLOCK content
            error_match = re.search(
                r"--- > ERROR BLOCK < ---\n(.*?)\n--- Context After", block, re.DOTALL
            )
            if error_match:
                error_content = error_match.group(1).strip()
                anomalies.add((anomaly_type, error_content))

        files[filename] = anomalies
    return files


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: uv run python scripts/diff_reports.py <old_report.md> <new_report.md>"
        )
        return

    old_path = Path(sys.argv[1])
    new_path = Path(sys.argv[2])

    old_data = parse_report(old_path)
    new_data = parse_report(new_path)

    all_files = set(old_data.keys()) | set(new_data.keys())

    print(f"# Report Diff: {old_path.name} -> {new_path.name}\n")

    for filename in sorted(all_files):
        old_anoms = old_data.get(filename, set())
        new_anoms = new_data.get(filename, set())

        resolved = old_anoms - new_anoms
        introduced = new_anoms - old_anoms

        if not resolved and not introduced:
            continue

        print(f"## {filename}")
        if resolved:
            print(f"✅ **Resolved ({len(resolved)}):**")
            for type, content in resolved:
                print(f'- [{type}] "{content[:60]}..."')

        if introduced:
            print(f"❌ **New/Remaining ({len(introduced)}):**")
            for type, content in introduced:
                print(f'- [{type}] "{content[:60]}..."')
        print()


if __name__ == "__main__":
    main()
