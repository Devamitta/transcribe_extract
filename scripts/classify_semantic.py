#!/usr/bin/env python3
"""Classify semantic evaluation report findings via direct LLM API call, with optional pro tier."""

import json
import sys
from pathlib import Path

from tools import printer as _p
from tools.ai_manager import AIManager
from tools.semantic_classify import (
    ClassificationError,
    build_classification_instruction,
    classify_findings,
    enforce_phonetic_coverage_rule,
    fetch_full_context,
    format_compact,
    load_carried_patterns,
    parse_report,
    resolve_transcript,
)

pr = _p.printer

REFERENCE_PATH = Path("kamma/enhance/data/enhance-semantic-reference.md")
OUTPUT_PATH = Path("temp/semantic_classifications.md")
PRO_BATCH_SIZE = 10


def _build_pro_instruction(fast_instruction: str, has_full_context: bool) -> str:
    """Augment the classification instruction for pro tier with full_context guidance."""
    extra = (
        "PRO TIER — REEVALUATION WITH FULLER CONTEXT:\n"
        "Each finding below includes a 'full_context' field containing the complete "
        "Whisper timestamp block (5–15 sentences) surrounding the flagged passage. "
        "Use this expanded context to judge phonetic plausibility — the extra sentences "
        "often reveal whether the correction is defensible from the speaker's actual words.\n"
    )
    if has_full_context:
        extra += (
            "If full_context is empty or extremely short, lean toward TP-defer. "
            "All standard PHONETIC COVERAGE RULE criteria still apply.\n\n"
        )
    else:
        extra += (
            "WARNING: Some items below may have has_context=false with a flag "
            '"[full_context unavailable]" — for these items, lean heavily toward TP-defer.\n\n'
        )
    return fast_instruction + "\n" + extra


def _render_pro_finding(item: dict[str, str]) -> str:
    """Render a single finding with full_context for pro tier input."""
    lines: list[str] = []
    lines.append(f"Passage: {item.get('passage', '')}")
    context = item.get("context", "")
    if context:
        lines.append(f"Context: {context}")
    lines.append(f"Issue: {item.get('issue', '')}")
    lines.append(f"Suggestion: {item.get('suggestion', '')}")
    full = item.get("full_context", "")
    if full:
        lines.append(f"full_context: {full}")
    else:
        lines.append("full_context: [full_context unavailable]")
    return "\n".join(lines)


def _render_pro_input(items: list[dict[str, str]]) -> str:
    """Render a batch of pro-tier items as numbered input."""
    blocks: list[str] = []
    for i, item in enumerate(items):
        blocks.append(f"### Finding {i + 1}")
        blocks.append(_render_pro_finding(item))
        blocks.append("")
    return "\n".join(blocks)


def _parse_pro_response(text: str) -> list[dict[str, str]]:
    """Parse pro tier LLM response, same format as classify_findings."""
    json_str = text.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:].strip()
    if json_str.endswith("```"):
        json_str = json_str[:-3].strip()

    items = json.loads(json_str)
    if not isinstance(items, list):
        raise ClassificationError("pro tier response JSON was not a list")

    classified: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ClassificationError("pro tier response item was not an object")
        classified.append({str(key): str(value) for key, value in item.items()})
    return classified


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv

    no_pro = False
    dry_run = False
    positional: list[str] = []

    for arg in raw_args:
        if arg == "--no-pro":
            no_pro = True
        elif arg == "--dry-run":
            dry_run = True
        elif arg == "--help":
            pr.green(
                "Usage: classify_semantic.py [--no-pro] [--dry-run] <report.md> [report2.md ...]"
            )
            return 0
        elif arg.startswith("--"):
            pr.no(f"Unknown flag: {arg}")
            return 1
        else:
            positional.append(arg)

    if not positional:
        pr.no(
            "Usage: classify_semantic.py [--no-pro] [--dry-run] <report.md> [report2.md ...]"
        )
        return 1

    report_paths = [Path(a) for a in positional]
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

    # Per-report defer items for pro tier
    defer_items: list[dict[str, str]] = []

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

        classified = enforce_phonetic_coverage_rule(classified)

        for item in classified:
            if item.get("classification") == "TP-defer":
                # Preserve original context/issue from raw findings
                matching = [
                    f
                    for f in raw_findings
                    if f.get("passage", "") == item.get("passage", "")
                ]
                if matching:
                    item["context"] = matching[0].get("context", "")
                    item["issue"] = matching[0].get("issue", "")

        all_results.extend(classified)
        processed += 1
        pr.yes(f"  {len(classified)} finding(s) classified")

    if not all_results:
        pr.no("No findings classified.")
        return 1 if failed else 0

    # --- Pro Tier ---
    if not no_pro:
        defer_items = [
            item for item in all_results if item.get("classification") == "TP-defer"
        ]
        if defer_items:
            pr.green(f"Pro tier: {len(defer_items)} TP-defer item(s) to reevaluate")
            pro_fixes: list[dict[str, str]] = []

            # Gather per-report defer items for batch context resolution
            by_report: dict[str, list[dict[str, str]]] = {}
            for item in defer_items:
                by_report.setdefault(item.get("_report", ""), []).append(item)

            # For each report, resolve transcript once
            for report_name, items in by_report.items():
                report_path = None
                for rp in report_paths:
                    if rp.name == report_name:
                        report_path = rp
                        break
                if report_path is None:
                    for item in items:
                        pr.amber(
                            f"[Pro tier] Skipping '{item['passage'][:40]}...' — report path not found"
                        )
                    continue

                transcript_path = resolve_transcript(report_path)
                if transcript_path is None:
                    for item in items:
                        pr.amber(
                            f"[Pro tier] Skipping '{item['passage'][:40]}...' — transcript not found"
                        )
                    continue

                # Fetch full_context for each item
                for item in items:
                    passage = item.get("passage", "")
                    ctx = fetch_full_context(passage, transcript_path)
                    if ctx:
                        item["full_context"] = ctx
                    else:
                        pr.amber(
                            f"[Pro tier] Skipping '{passage[:40]}...' — context not found in file"
                        )

            # Collect all defer items that have a passage (even those without full_context)
            pro_candidates = [item for item in defer_items if item.get("passage")]

            if pro_candidates:
                # Batch by 10
                has_any_context = any(
                    item.get("full_context") for item in pro_candidates
                )
                pro_instruction = _build_pro_instruction(instruction, has_any_context)

                if dry_run:
                    pr.green(
                        f"[dry-run] Would send {len(pro_candidates)} item(s) in "
                        f"{(len(pro_candidates) + PRO_BATCH_SIZE - 1) // PRO_BATCH_SIZE} "
                        f"batch(es) to pro model"
                    )
                    for i in range(0, len(pro_candidates), PRO_BATCH_SIZE):
                        batch = pro_candidates[i : i + PRO_BATCH_SIZE]
                        pr.amber(
                            f"  Batch {i // PRO_BATCH_SIZE + 1}: {len(batch)} item(s)"
                        )
                else:
                    manager = AIManager()
                    total_batches = (
                        len(pro_candidates) + PRO_BATCH_SIZE - 1
                    ) // PRO_BATCH_SIZE
                    for batch_idx in range(total_batches):
                        batch = pro_candidates[
                            batch_idx * PRO_BATCH_SIZE : (batch_idx + 1)
                            * PRO_BATCH_SIZE
                        ]
                        pr.bip()
                        input_text = _render_pro_input(batch)
                        try:
                            response = manager.generate_pro(
                                contents=input_text,
                                system_instruction=pro_instruction,
                            )
                            if not response.content or not response.content.strip():
                                pr.amber(
                                    f"[Pro tier] Batch {batch_idx + 1}/{total_batches}: empty response"
                                )
                                continue

                            try:
                                pro_classified = _parse_pro_response(response.content)
                            except (ClassificationError, json.JSONDecodeError) as exc:
                                pr.amber(
                                    f"[Pro tier] Batch {batch_idx + 1}/{total_batches}: "
                                    f"parse failed — {exc}"
                                )
                                continue

                            # Match pro results back by passage
                            passage_to_result: dict[str, dict[str, str]] = {}
                            for pc in pro_classified:
                                passage_to_result[pc.get("passage", "")] = pc

                            batch_fixes = 0
                            for item in batch:
                                passage = item.get("passage", "")
                                pro_result = passage_to_result.get(passage)
                                if (
                                    pro_result
                                    and pro_result.get("classification") == "TP-fix"
                                ):
                                    item["classification"] = "TP-fix"
                                    existing = item.get("reason", "")
                                    pro_reason = pro_result.get("reason", "")
                                    item["reason"] = (
                                        f"{existing} [Pro tier] {pro_reason}".strip()
                                    )
                                    pro_fixes.append(item)
                                    batch_fixes += 1

                            pr.yes(
                                f"  Batch {batch_idx + 1}/{total_batches}: "
                                f"{batch_fixes} pro fix(es) out of {len(batch)}"
                            )
                        except Exception as exc:
                            pr.amber(
                                f"[Pro tier] Batch {batch_idx + 1}/{total_batches}: "
                                f"request failed — {exc}"
                            )

                if pro_fixes:
                    pr.green(f"Pro tier added {len(pro_fixes)} fix(es)")
    else:
        pr.amber("Pro tier skipped (--no-pro)")

    if dry_run:
        pr.green("[dry-run] No output file written")
        return 0

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
