"""Evaluates post-Pali-correction transcripts for semantic hallucinations using an LLM."""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from tools import printer as _p
from tools.pali import chunk_text_no_overlap, get_semantic_eval_instruction
from tools.provider import TEST_MODE, generate_content, get_working_key

pr = _p.printer


def evaluate_chunk(chunk: str) -> list[dict]:
    instruction = get_semantic_eval_instruction()
    try:
        result = generate_content(contents=chunk, system_instruction=instruction)
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

    SEMANTIC_REPORT_DIR = Path("reports/semantic")
    queue = []
    skipped = 0

    for file_path in md_files:
        try:
            rel = file_path.relative_to(input_dir)
            output_path = SEMANTIC_REPORT_DIR / rel
        except ValueError:
            output_path = SEMANTIC_REPORT_DIR / file_path.name
        output_path_flat = SEMANTIC_REPORT_DIR / file_path.name

        if output_path.exists() or output_path_flat.exists():
            pr.amber(f"[SKIP] {file_path.name}")
            skipped += 1
        else:
            queue.append(file_path)

    if skipped:
        pr.info(f"{skipped} already done, {len(queue)} to process")

    if not queue:
        pr.yes("All files already evaluated. Nothing to do.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(f"reports/semantic_anomalies_{timestamp}.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_lines = [f"# Semantic Evaluation Report — {timestamp}\n"]

    total_findings = 0

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

        if file_findings:
            report_lines.append(f"## {file_path.name}\n")
            for item in file_findings:
                report_lines.append(f"### Passage\n> {item.get('passage', '')}\n")
                report_lines.append(f"**Issue:** {item.get('issue', '')}\n")
                report_lines.append(
                    f"**Suggestion:** {item.get('suggestion', '')}\n\n---\n"
                )
            total_findings += len(file_findings)
            pr.yes(f"{file_path.name} — {len(file_findings)} issue(s)")
        else:
            pr.yes(f"{file_path.name} — clean")

        time.sleep(5)

    report_lines.append(
        f"\n## Summary\n- Files: {len(md_files)}\n- Total issues: {total_findings}"
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    pr.yes(f"Report: {report_path}")


if __name__ == "__main__":
    if not get_working_key():
        pr.no("No API key.")
        exit(1)
    main()
