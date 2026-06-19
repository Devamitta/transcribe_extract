#!/usr/bin/env python3
"""Evaluates post-Pali-correction transcripts for semantic hallucinations using an LLM."""

import concurrent.futures
import json
import sys
import time
from pathlib import Path

from tools import printer as _p
from tools.incremental import finalize_temp, get_temp_path, load_temp, save_temp
from tools.pali import chunk_text_no_overlap, get_semantic_eval_instruction
from tools.provider import (
    TEST_MODE,
    build_cacheable_contents,
    generate_with_timeout,
)

pr = _p.printer

INTER_CHUNK_SLEEP_SECONDS = 2.0
INTER_FILE_SLEEP_SECONDS = 5.0


class SemanticEvaluationError(RuntimeError):
    """Raised when a semantic evaluation chunk cannot be evaluated safely."""


def evaluate_chunk(chunk: str) -> list[dict[str, str]]:
    instruction = get_semantic_eval_instruction()
    try:
        result = generate_with_timeout(
            contents=build_cacheable_contents(chunk),
            system_instruction=instruction,
        )
        if not result or not result.strip():
            raise SemanticEvaluationError("empty response from LLM")

        json_str = result.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:].strip()
        if json_str.endswith("```"):
            json_str = json_str[:-3].strip()

        items = json.loads(json_str)
    except SemanticEvaluationError:
        raise
    except concurrent.futures.TimeoutError as exc:
        raise SemanticEvaluationError("timeout") from exc
    except json.JSONDecodeError as exc:
        raise SemanticEvaluationError(f"invalid JSON: {exc}") from exc
    except Exception as exc:
        raise SemanticEvaluationError(f"request failed: {exc}") from exc

    if not isinstance(items, list):
        raise SemanticEvaluationError("semantic response JSON was not a list")

    findings: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise SemanticEvaluationError("semantic response item was not an object")
        findings.append({str(key): str(value) for key, value in item.items()})
    return findings


def get_report_paths(file_path: Path, input_dir: Path) -> tuple[Path, Path, str]:
    try:
        rel = file_path.relative_to(input_dir)
        report_path = Path("reports/semantic") / rel
        rel_stem = str(rel.with_suffix(""))
    except ValueError:
        report_path = Path("reports/semantic") / file_path.name
        rel_stem = file_path.stem

    flat_report_path = Path("reports/semantic") / file_path.name
    return report_path, flat_report_path, rel_stem


def report_is_current(
    report_path: Path, flat_report_path: Path, source_path: Path
) -> bool:
    source_mtime = source_path.stat().st_mtime

    if report_path.exists() and report_path.stat().st_mtime >= source_mtime:
        return True

    if flat_report_path.exists() and flat_report_path.stat().st_mtime >= source_mtime:
        return True

    return False


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    args = [a for a in raw_args if not a.startswith("-")]
    specific = args[0] if args else None
    input_dir = Path("output/corrected_pali")

    if specific:
        path = Path(specific)
        if not path.is_absolute() and not path.exists():
            path = input_dir / specific

        if not path.exists():
            pr.no(f"Not found: {path}")
            return 1

        md_files = sorted(path.rglob("*.md")) if path.is_dir() else [path]
    else:
        md_files = sorted(input_dir.rglob("*.md"))

    if not md_files:
        pr.no("No files found.")
        return 0

    pr.green(f"Found {len(md_files)} file(s)")

    queue = []
    skipped = 0

    for file_path in md_files:
        output_path, output_path_flat, _ = get_report_paths(file_path, input_dir)

        if report_is_current(output_path, output_path_flat, file_path):
            pr.amber(f"[SKIP] {file_path.name}")
            skipped += 1
        else:
            queue.append(file_path)

    if skipped:
        pr.green(f"{skipped} already done, {len(queue)} to process")

    if not queue:
        pr.yes("All files already evaluated. Nothing to do.")
        return 0

    failed_files = 0
    for file_path in queue:
        pr.green(f"Processing {file_path.name}...")
        text = file_path.read_text(encoding="utf-8")
        chunks = chunk_text_no_overlap(text, chunk_size=5000)
        if TEST_MODE:
            chunks = chunks[:2]

        out_path, _, rel_stem = get_report_paths(file_path, input_dir)
        temp_path = get_temp_path(out_path)
        chunk_results: list[list[dict[str, str]]] = load_temp(temp_path)
        start = len(chunk_results)

        if 0 < start < len(chunks):
            pr.green(f"  Resuming from chunk {start + 1}/{len(chunks)}...")

        file_failed = False
        for i, chunk in enumerate(chunks):
            if i < start:
                continue
            pr.green(f"  Chunk {i + 1}/{len(chunks)}...")
            try:
                results = evaluate_chunk(chunk)
            except SemanticEvaluationError as exc:
                pr.no(f"  Chunk {i + 1} failed: {exc}")
                file_failed = True
                break
            chunk_results.append(results)
            save_temp(temp_path, chunk_results)
            time.sleep(INTER_CHUNK_SLEEP_SECONDS)

        if file_failed:
            failed_files += 1
            pr.no(f"{file_path.name} — failed; semantic report not written")
            continue

        file_findings = [item for sublist in chunk_results for item in sublist]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        report_text = f"# Semantic Evaluation: {rel_stem}\n\n"

        if file_findings:
            for item in file_findings:
                report_text += f"## Passage\n> {item.get('passage', '')}\n\n"
                report_text += f"**Issue:** {item.get('issue', '')}\n\n"
                report_text += (
                    f"**Suggestion:** {item.get('suggestion', '')}\n\n---\n\n"
                )
            pr.yes(f"{file_path.name} — {len(file_findings)} issue(s) → {out_path}")
        else:
            report_text += "_No anomalies detected._\n"
            pr.yes(f"{file_path.name} — clean")

        out_path.write_text(report_text, encoding="utf-8")
        finalize_temp(temp_path)

        time.sleep(INTER_FILE_SLEEP_SECONDS)

    return 1 if failed_files else 0


if __name__ == "__main__":
    raise SystemExit(main())
