#!/usr/bin/env python3
"""Detects and reports Whisper transcription errors like word loops, punctuation spam, and low-entropy text."""

import argparse
import re
from pathlib import Path

# Regex definitions for Whisper failure modes
REPEATED_WORDS_PATTERN = re.compile(r"\b(\w+)(?:\s+\1){3,}\b", re.IGNORECASE)
PUNCTUATION_SPAM_PATTERN = re.compile(r"[.,!?\-_]{6,}")


def identify_anomaly(text: str) -> str | None:
    """Evaluates a text block and returns the error type if a threshold is met."""
    # Strip the timestamp (e.g., "[12.3]") to prevent false entropy readings
    clean_text = re.sub(r"^\[\d+\.\d+\]\s*", "", text.strip())

    if not clean_text:
        return None

    if PUNCTUATION_SPAM_PATTERN.search(clean_text):
        return "Punctuation/Symbol Spam"

    if REPEATED_WORDS_PATTERN.search(clean_text):
        return "Word Loop Hallucination"

    # Low entropy check: strings > 30 chars with fewer than 6 unique characters
    if len(clean_text) > 30 and len(set(clean_text)) < 6:
        return "Low Entropy Character Spam"

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Extract Whisper hallucinations with context from markdown transcripts."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="output/transcribed",
        help="Directory containing .md transcripts",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="error_report.md",
        help="Path to save the generated report",
    )
    parser.add_argument(
        "--context-blocks",
        type=int,
        default=1,
        help="Number of paragraphs to extract before and after the error",
    )
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    md_files = list(input_path.glob("*.md"))

    if not md_files:
        print(f"Error: No .md files found in {args.input_dir}")
        return

    report_lines = ["# Whisper Transcription Error Report\n"]
    total_anomalies = 0

    for file_path in md_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split by double newline to isolate timestamped paragraphs
        blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
        file_anomalies = []

        for i, block in enumerate(blocks):
            anomaly_type = identify_anomaly(block)

            if anomaly_type:
                total_anomalies += 1
                # Grab surrounding context
                start_idx = max(0, i - args.context_blocks)
                end_idx = min(len(blocks), i + args.context_blocks + 1)

                context_before = (
                    "\n\n".join(blocks[start_idx:i])
                    if start_idx < i
                    else "[Start of File]"
                )
                context_after = (
                    "\n\n".join(blocks[i + 1 : end_idx])
                    if end_idx > i + 1
                    else "[End of File]"
                )

                file_anomalies.append(
                    {
                        "type": anomaly_type,
                        "before": context_before,
                        "error": block,
                        "after": context_after,
                    }
                )

        if file_anomalies:
            report_lines.append(f"## File: {file_path.name}")
            for idx, anom in enumerate(file_anomalies):
                report_lines.append(f"\n### Anomaly {idx + 1}: {anom['type']}")
                report_lines.append("```text")
                report_lines.append(f"--- Context Before ---\n{anom['before']}\n")
                report_lines.append(f"--- > ERROR BLOCK < ---\n{anom['error']}\n")
                report_lines.append(f"--- Context After  ---\n{anom['after']}")
                report_lines.append("```\n")

    with open(args.output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(
        f"Extraction complete. Found {total_anomalies} anomalies across {len(md_files)} files."
    )
    print(f"Report saved to: {args.output_file}")


if __name__ == "__main__":
    main()
