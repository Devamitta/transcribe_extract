"""Evaluates post-Pali-correction transcripts for semantic hallucinations using an LLM."""

import json
import sys
import time
from pathlib import Path

from tools import printer as _p
from tools.pali import chunk_text_no_overlap, get_semantic_eval_instruction
from tools.provider import (
    TEST_MODE,
    build_cacheable_contents,
    generate_content,
    get_working_key,
)

pr = _p.printer


def evaluate_chunk(chunk: str) -> list[dict[str, str]]:
    instruction = get_semantic_eval_instruction()
    try:
        result = generate_content(
            contents=build_cacheable_contents(chunk),
            system_instruction=instruction,
        )
        if not result:
            pr.warning("Empty response from LLM.")
            return []

        json_str = result.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:].strip()
        if json_str.endswith("```"):
            json_str = json_str[:-3].strip()

        items = json.loads(json_str)
        if isinstance(items, list):
            return items
        return []
    except Exception as e:
        pr.warning(f"Parse failed: {e}")
        return []


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


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    specific = args[0] if args else None
    input_dir = Path("output/corrected_pali")

    if specific:
        path = Path(specific)
        if not path.is_absolute() and not path.exists():
            path = input_dir / specific

        if not path.exists():
            pr.no(f"Not found: {path}")
            return

        md_files = sorted(path.rglob("*.md")) if path.is_dir() else [path]
    else:
        md_files = sorted(input_dir.rglob("*.md"))

    if not md_files:
        pr.no("No files found.")
        return

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
        pr.info(f"{skipped} already done, {len(queue)} to process")

    if not queue:
        pr.yes("All files already evaluated. Nothing to do.")
        return

    for file_path in queue:
        pr.green(f"Processing {file_path.name}...")
        text = file_path.read_text(encoding="utf-8")
        chunks = chunk_text_no_overlap(text, chunk_size=5000)
        if TEST_MODE:
            chunks = chunks[:2]

        file_findings = []
        for i, chunk in enumerate(chunks):
            pr.green(f"  Chunk {i + 1}/{len(chunks)}...")
            results = evaluate_chunk(chunk)
            file_findings.extend(results)
            time.sleep(2)

        # Write per-file report matching batch.py semantic output.
        out_path, _, rel_stem = get_report_paths(file_path, input_dir)

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

        time.sleep(5)


if __name__ == "__main__":
    if not get_working_key():
        pr.no("No API key.")
        exit(1)
    main()
