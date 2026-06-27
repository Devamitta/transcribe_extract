#!/usr/bin/env python3
"""Classify semantic evaluation report findings via direct LLM API call."""

import sys
from pathlib import Path

from tools import printer as _p
from tools.semantic_classify import (
    ClassificationError,
    build_classification_instruction,
    classify_findings,
    enforce_single_word_rule,
    format_compact,
    load_carried_patterns,
    parse_report,
)

pr = _p.printer

REFERENCE_PATH = Path("kamma/enhance/data/enhance-semantic-reference.md")
OUTPUT_PATH = Path("temp/semantic_classifications.md")


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    if not raw_args:
        pr.no("Usage: classify_semantic.py <report.md> [report2.md ...]")
        return 1

    report_paths = [Path(a) for a in raw_args]
    missing = [p for p in report_paths if not p.exists()]
    if missing:
        for p in missing:
            pr.no(f"Not found: {p}")
        return 1

    carried_patterns = load_carried_patterns()
    reference_md = ""
    if REFERENCE_PATH.exists():
        reference_md = REFERENCE_PATH.read_text(encoding="utf-8")

    instruction = build_classification_instruction(carried_patterns, reference_md)

    all_results: list[dict[str, str]] = []
    failed = 0
    processed = 0

    for report_path in report_paths:
        pr.green(f"Classifying {report_path.name}...")
        pr.bip()

        try:
            raw_findings = parse_report(report_path)
        except Exception as exc:
            pr.no(f"  parse failed: {exc}")
            failed += 1
            continue

        if not raw_findings:
            pr.amber("  no findings to classify")
            processed += 1
            continue

        try:
            classified = classify_findings(raw_findings, instruction)
        except ClassificationError as exc:
            pr.no(f"  classification failed: {exc}")
            failed += 1
            continue

        suggestion_map = {
            f.get("passage", ""): f.get("suggestion", "") for f in raw_findings
        }
        for item in classified:
            item["suggestion"] = suggestion_map.get(item.get("passage", ""), "")
            item["_report"] = report_path.name

        classified = enforce_single_word_rule(classified)
        all_results.extend(classified)
        processed += 1
        pr.yes(f"  {len(classified)} finding(s) classified")

    if not all_results:
        pr.no("No findings classified.")
        return 1 if failed else 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sections: list[str] = []
    seen_reports: dict[str, list[dict[str, str]]] = {}
    for item in all_results:
        report_name = item.pop("_report", "unknown")
        seen_reports.setdefault(report_name, []).append(item)

    for report_name, items in seen_reports.items():
        sections.append(f"## {report_name}\n")
        sections.append(format_compact(items))
        sections.append("")

    OUTPUT_PATH.write_text("\n".join(sections), encoding="utf-8")
    pr.yes(f"Wrote {len(all_results)} classifications to {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
