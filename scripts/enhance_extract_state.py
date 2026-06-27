#!/usr/bin/env python3
"""Extract filtered sections from enhance-state.md. Gatekeeper for Pro-tier skills."""

import argparse
import re
import sys
from pathlib import Path

from tools import printer


def resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def extract_section(text: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def filter_by_stage(section_text: str, stage: str) -> str:
    if not section_text:
        return ""

    lines = section_text.split("\n")
    matched: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.search(
            rf"\[stage:\s*{re.escape(stage)}\]",
            stripped,
            re.IGNORECASE,
        ):
            matched.append(stripped)

    return "\n".join(matched)


def extract_routing_handoffs(text: str) -> str:
    section = extract_section(text, "Routing Handoffs")
    if not section:
        return ""

    lines = section.strip().split("\n")
    entries: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("-"):
            entries.append(stripped)
            if len(entries) >= 10:
                break

    return "\n".join(entries)


def extract_active_backlog(text: str) -> str:
    section = extract_section(text, "Active Backlog")
    if not section:
        return ""

    return section.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract filtered sections from enhance-state.md."
    )
    parser.add_argument(
        "--section",
        required=True,
        choices=["carried_patterns", "routing_handoffs", "active_backlog"],
        help="Which section to extract.",
    )
    parser.add_argument(
        "--stage",
        default=None,
        choices=["extract", "polish", "pali", "semantic"],
        help="Filter Carried Patterns by stage tag.",
    )
    parser.add_argument(
        "--hub",
        type=Path,
        default=None,
        help="Path to enhance-state.md (default: kamma/enhance/enhance-state.md relative to repo root).",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = resolve_repo_root()
    hub_path = args.hub or (root / "kamma" / "enhance" / "enhance-state.md")

    pr = printer.printer

    if not hub_path.exists():
        pr.amber(f"Hub file not found: {hub_path}")
        return 0

    text = hub_path.read_text(encoding="utf-8")

    if args.section == "carried_patterns":
        section = extract_section(text, "Carried Patterns")
        if args.stage:
            section = filter_by_stage(section, args.stage)
        if section:
            print(section)
        else:
            print("(empty)")
    elif args.section == "routing_handoffs":
        result = extract_routing_handoffs(text)
        if result:
            print(result)
        else:
            print("(empty)")
    elif args.section == "active_backlog":
        result = extract_active_backlog(text)
        if result:
            print(result)
        else:
            print("(empty)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
