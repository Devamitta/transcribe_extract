#!/usr/bin/env python3
"""Systematically compares original and corrected transcripts to detect LLM hallucinations and errors."""

import argparse
import difflib
import re
from datetime import datetime
from pathlib import Path

# Try to import glossary for over-correction detection
try:
    from tools.pali import PALI_GLOSSARY

    GLOSSARY_SET = {w.lower().strip() for w in PALI_GLOSSARY.split(",")}
except ImportError:
    GLOSSARY_SET = set()


def get_words(text: str) -> list[str]:
    """Extracts words from text, ignoring punctuation."""
    return re.findall(r"\b\w+\b", text.lower())


def evaluate_diff(original: str, corrected: str) -> dict[str, any]:
    """Compares two chunks of text and returns a dictionary of anomalies."""
    anomalies = []

    # 1. Check for Conversational AI Text
    ai_starters = [
        "here is",
        "i have",
        "sure",
        "corrected",
        "i've",
        "this is",
        "the following",
    ]
    corrected_lower = corrected.lower().strip()
    for starter in ai_starters:
        if corrected_lower.startswith(starter):
            anomalies.append(f"Conversational AI Starter: '{corrected[:50]}...'")
            break

    # 2. Check for Markdown Formatting Injection
    if "```" in corrected and "```" not in original:
        anomalies.append("Markdown Code Block Injection detected.")

    # 3. Massive Length Discrepancy (> 15%)
    orig_len = len(original)
    corr_len = len(corrected)
    if orig_len > 0:
        diff_percent = abs(orig_len - corr_len) / orig_len
        if diff_percent > 0.15:
            anomalies.append(
                f"Massive Length Discrepancy: {diff_percent:.1%} ({orig_len} -> {corr_len} chars)"
            )

    # 4. Word Discrepancy (Non-Pali)
    # This is a bit complex but we can do a basic check
    orig_words = get_words(original)
    corr_words = get_words(corrected)

    # If word counts differ significantly, it might be a hallucination
    if len(orig_words) > 0:
        word_diff_percent = abs(len(orig_words) - len(corr_words)) / len(orig_words)
        if word_diff_percent > 0.10:
            anomalies.append(
                f"Significant Word Count Change: {word_diff_percent:.1%} ({len(orig_words)} -> {len(corr_words)} words)"
            )

    # 5. Check if chunk is missing or extremely short
    if len(corrected_lower) < 20 and len(original) > 100:
        anomalies.append("Corrected chunk is suspiciously short compared to original.")

    # 6. Check for "Buddhicizing" (Over-correction)
    if GLOSSARY_SET:
        orig_words_set = set(orig_words)
        corr_words_set = set(corr_words)

        orig_glossary_matches = len(orig_words_set.intersection(GLOSSARY_SET))
        corr_glossary_matches = len(corr_words_set.intersection(GLOSSARY_SET))

        # Words we don't want to see replaced by Pali if they were in English
        TARGET_SENSITIVE_WORDS = {
            "mind",
            "meditation",
            "project",
            "merit",
            "wisdom",
            "suffering",
            "monk",
            "nun",
            "monastery",
        }
        deleted_sensitive = TARGET_SENSITIVE_WORDS.intersection(
            orig_words_set - corr_words_set
        )

        # If we gain many glossary terms AND lose sensitive English words, flag it
        if corr_glossary_matches > orig_glossary_matches + 2 and deleted_sensitive:
            anomalies.append(
                f"Potential Over-correction: {orig_glossary_matches} -> {corr_glossary_matches} glossary terms, deleted {deleted_sensitive}"
            )

    return anomalies


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Pali phonetic correction performance."
    )
    parser.add_argument(
        "--original-dir",
        type=str,
        default="output/transcribed",
        help="Original transcripts dir",
    )
    parser.add_argument(
        "--corrected-dir",
        type=str,
        default="output/corrected_pali",
        help="Corrected transcripts dir",
    )
    parser.add_argument("--output-report", type=str, help="Custom output report path")
    args = parser.parse_args()

    orig_dir = Path(args.original_dir)
    corr_dir = Path(args.corrected_dir)

    if not orig_dir.exists():
        print(f"Error: Original directory '{orig_dir}' does not exist.")
        return
    if not corr_dir.exists():
        print(f"Error: Corrected directory '{corr_dir}' does not exist.")
        return

    # Find all .md files in orig_dir
    orig_files = sorted(list(orig_dir.rglob("*.md")))
    if not orig_files:
        print(f"No .md files found in {orig_dir}")
        return

    report_path = (
        Path(args.output_report)
        if args.output_report
        else Path(
            f"reports/evaluate_pali_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_lines = [
        f"# Pali Correction Evaluation Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    ]
    total_files = 0
    total_anomalies = 0

    for orig_file in orig_files:
        relative_path = orig_file.relative_to(orig_dir)
        corr_file = corr_dir / relative_path

        if not corr_file.exists():
            continue

        total_files += 1
        file_anomalies = []

        orig_text = orig_file.read_text(encoding="utf-8")
        corr_text = corr_file.read_text(encoding="utf-8")

        orig_chunks = [c.strip() for c in orig_text.split("\n\n") if c.strip()]
        corr_chunks = [c.strip() for c in corr_text.split("\n\n") if c.strip()]

        if len(orig_chunks) != len(corr_chunks):
            file_anomalies.append(
                f"CRITICAL: Chunk count mismatch! Original: {len(orig_chunks)}, Corrected: {len(corr_chunks)}"
            )
            # We can't easily compare if counts differ, so we'll just flag it and continue with min count

        for i in range(min(len(orig_chunks), len(corr_chunks))):
            anomalies = evaluate_diff(orig_chunks[i], corr_chunks[i])
            if anomalies:
                file_anomalies.append(
                    {
                        "chunk": i + 1,
                        "anomalies": anomalies,
                        "original": orig_chunks[i],
                        "corrected": corr_chunks[i],
                    }
                )

        if file_anomalies:
            report_lines.append(f"## File: {relative_path}")
            for item in file_anomalies:
                if isinstance(item, str):
                    report_lines.append(f"- {item}")
                    continue

                total_anomalies += len(item["anomalies"])
                report_lines.append(f"### Chunk {item['chunk']} Anomalies:")
                for a in item["anomalies"]:
                    report_lines.append(f"- {a}")

                report_lines.append("\n#### Diff Summary:")
                diff = difflib.ndiff(
                    item["original"].splitlines(), item["corrected"].splitlines()
                )
                report_lines.append("```diff")
                report_lines.append("\n".join(diff))
                report_lines.append("```\n")

    report_lines.append(
        f"\n## Summary\n- Files evaluated: {total_files}\n- Total anomalies flagged: {total_anomalies}"
    )

    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(
        f"Evaluation complete. Found {total_anomalies} anomalies across {total_files} files."
    )
    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()
