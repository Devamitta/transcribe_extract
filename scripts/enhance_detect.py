#!/usr/bin/env python3
"""State detection for enhance pipeline: file counts, open patterns, unreviewed semantic reports."""

import argparse
import json
import re
import sys
from pathlib import Path

from tools import printer


def resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def count_files(dir_path: Path) -> int:
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    return len([f for f in dir_path.glob("*.md") if f.is_file()])


def count_semantic_files(dir_path: Path) -> int:
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    count = 0
    for f in dir_path.glob("*.md"):
        if f.is_file():
            count += 1
    return count


def compute_unreviewed(semantic_dir: Path, ledger_path: Path) -> int:
    on_disk = count_semantic_files(semantic_dir)
    if not ledger_path.exists():
        return on_disk
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return on_disk
    processed = ledger.get("processed_files", [])
    return max(0, on_disk - len(processed))


def parse_open_patterns(hub_path: Path) -> list[dict[str, object]]:
    if not hub_path.exists():
        return []

    text = hub_path.read_text(encoding="utf-8")

    carried_match = re.search(
        r"##\s+Carried\s+Patterns\s*\n(.*?)(?=\n##\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not carried_match:
        return []

    section = carried_match.group(1)
    items: list[dict[str, object]] = []

    lines = section.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        open_match = re.search(r"\(open,\s*(\d{4}-\d{2}-\d{2})\)", stripped)
        if not open_match:
            continue

        stage_match = re.search(r"\[stage:\s*(.+?)\]", stripped, re.IGNORECASE)
        if not stage_match:
            continue

        stages_raw = stage_match.group(1)
        pattern = stripped.lstrip("- ").strip()

        stages = [s.strip() for s in stages_raw.split(",")]

        items.append(
            {
                "stage": stages[0] if stages else "unknown",
                "all_stages": stages,
                "pattern": pattern,
                "date": open_match.group(1),
            }
        )

    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect enhance pipeline state.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root path (default: auto-detected from script location).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON only (no printer output)."
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = args.root or resolve_repo_root()
    json_only = args.json

    corrected_dir = root / "output" / "corrected_pali" / "interview"
    extracted_dir = root / "output" / "extracted" / "interview"
    polished_dir = root / "output" / "polished" / "interview"
    semantic_dir = root / "reports" / "semantic" / "interview"
    ledger_path = root / "kamma" / "enhance" / "data" / "semantic-ledger.json"
    hub_path = root / "kamma" / "enhance" / "enhance-state.md"

    corrected_count = count_files(corrected_dir)
    extracted_count = count_files(extracted_dir)
    polished_count = count_files(polished_dir)
    unreviewed_semantic = compute_unreviewed(semantic_dir, ledger_path)
    open_patterns = parse_open_patterns(hub_path)

    result: dict = {
        "corrected_count": corrected_count,
        "extracted_count": extracted_count,
        "polished_count": polished_count,
        "unreviewed_semantic": unreviewed_semantic,
        "open_patterns": open_patterns,
    }

    if json_only:
        print(json.dumps(result, indent=2))
    else:
        pr = printer.printer
        pr.green(f"Corrected Pāli:  {corrected_count}")
        pr.green(f"Extracted:       {extracted_count}")
        pr.green(f"Polished:        {polished_count}")
        pr.green(f"Unreviewed sem.: {unreviewed_semantic}")
        if open_patterns:
            pr.amber(f"Open patterns:   {len(open_patterns)}")
            for p in open_patterns:
                stage = p.get("stage", "unknown")
                pattern = p.get("pattern", "")
                if isinstance(pattern, str):
                    pr.amber(f"  [{stage}] {pattern[:100]}")
        else:
            pr.yes("Open patterns: 0")
        print()
        print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
