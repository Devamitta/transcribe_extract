#!/usr/bin/env python3
"""Detects and reports Whisper transcription errors like word loops, punctuation spam, and low-entropy text."""

import argparse
import re
from datetime import datetime
from pathlib import Path

# Regex definitions for Whisper failure modes
REPEATED_WORDS_PATTERN = re.compile(r"\b(\w+)(?:\s+\1){3,}\b", re.IGNORECASE)
PUNCTUATION_SPAM_PATTERN = re.compile(r"[.,!?\-_]{6,}")


def identify_anomaly(text: str) -> str | None:
    """Evaluates a text block and returns the error type if a threshold is met."""
    # Check for large whitespace gaps before cleaning
    if re.search(r"\s{5,}", text):
        return "Large Whitespace Gap"

    # Strip the timestamp (e.g., "[12.3]") to prevent false entropy readings
    clean_text = re.sub(r"^\[\d+\.\d+\]\s*", "", text.strip())

    if not clean_text:
        return None

    if PUNCTUATION_SPAM_PATTERN.search(clean_text):
        return "Punctuation/Symbol Spam"

    # Punctuation-agnostic Word Loop Hallucination (e.g. "word, word, word, word")
    clean_text_only = re.sub(r"[^\w\s]", "", clean_text).strip()
    match = re.search(r"\b(\w+)( \1){3,}\b", clean_text_only, re.IGNORECASE)
    if match:
        word = match.group(1).lower()
        # Whitelist filler words that are common in natural stutters.
        # Allow up to 5 repetitions (word + 4 repeats). Filter if 6 or more (word + 5 repeats).
        filler_whitelist = [
            "yeah",
            "no",
            "okay",
            "so",
            "right",
            "hmm",
            "mhmm",
            "for",
            "and",
            "but",
            "like",
            "i",
            "it",
            "they",
            "we",
            "you",
        ]
        if word in filler_whitelist:
            if re.search(r"\b(\w+)( \1){5,}\b", clean_text_only, re.IGNORECASE):
                return "Word Loop Hallucination"
        else:
            return "Word Loop Hallucination"

    # Catches sentence-level loops (Tiered approach to reduce false positives from stutters)
    # 1. Long phrases (>30 chars) repeating once
    if re.search(r"(.{30,})\1{1,}", clean_text, re.IGNORECASE):
        return "Sentence Loop Hallucination"
    # 2. Medium phrases (15-30 chars) repeating twice (appears 3 times)
    if re.search(r"(.{15,30})\1{2,}", clean_text, re.IGNORECASE):
        return "Sentence Loop Hallucination"

    # Low entropy check: strings > 30 chars with fewer than 6 unique characters
    if len(clean_text) > 30 and len(set(clean_text)) < 6:
        return "Low Entropy Character Spam"

    # Flag suspiciously short or isolated lines (expanded silence hallucinations)
    if len(clean_text) < 15 and (
        not re.search(r"[.!?,]", clean_text)
        or clean_text.lower().strip(".!?,\"' ")
        in [
            "help",
            "so",
            "yeah",
            "a",
            "okay",
            "you know",
            "i mean",
            "what",
            "no",
            "yes",
            "promise",
            "exactly",
            "right",
        ]
    ):
        return "Isolated Short Line (Silence Hallucination?)"

    # Check for suspicious null characters
    if "\x00" in clean_text:
        return "Suspicious Characters"

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
        default=f"reports/error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
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
    md_files = sorted(list(input_path.rglob("*.md")))

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

    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(
        f"Extraction complete. Found {total_anomalies} anomalies across {len(md_files)} files."
    )
    if total_anomalies == 0:
        print("All good! No anomalies found.")
    print(f"Report saved to: {args.output_file}")


if __name__ == "__main__":
    main()
