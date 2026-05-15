#!/usr/bin/env python3
"""Transcribes MP3 audio files to markdown using MLX Whisper with context-specific Pali vocabulary prompts."""

import argparse
import re
import time
from pathlib import Path
from typing import Any

import mlx_whisper


from tools.glossary import DHAMMA, SANGHA, VINAYA

VOCAB_PROMPTS = {
    "sangha": f"Buddhist Saṅgha discussion. Pali terms: {', '.join(SANGHA)}",
    "dhamma": f"Buddhist Dhamma class. Pali terms: {', '.join(DHAMMA)}",
    "vinaya": f"Buddhist Vinaya class. Pali terms: {', '.join(VINAYA)}",
    "interview": f"Buddhist meditation interview. Pali terms: {', '.join(DHAMMA)}",
    "russian": "Буддийская лекция о Дхамме. Pali terms: Nibbāna, Satipaṭṭhāna, Dhamma, Saṅgha",
}


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe raw audio files using MLX Whisper with context-specific Pali glossaries."
    )
    # Changed default input dir to the raw audio folder
    parser.add_argument(
        "--input-dir",
        type=str,
        default="audio",
        help="Directory containing raw audio files (default: audio)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save transcription markdown files (default: output/transcribed/<input-dir-name>)",
    )
    parser.add_argument(
        "--context",
        type=str,
        choices=["sangha", "dhamma", "vinaya", "interview", "russian"],
        default="interview",
        help="Select the Pali vocabulary context.",
    )
    parser.add_argument(
        "--test-run",
        action="store_true",
        help="If active, only transcribe the first file found (for testing).",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=60,
        help="Paragraph flush interval in seconds (default: 60). Use 30 for finer YouTube chapter timestamps.",
    )
    args = parser.parse_args()

    chunk_seconds = float(args.chunk_seconds)
    audio_dir = Path(args.input_dir)
    if args.output_dir:
        output_dir = Path(args.output_dir)
    elif audio_dir.is_relative_to("audio"):
        output_dir = Path("output/transcribed") / audio_dir.relative_to("audio")
    else:
        output_dir = Path("output/transcribed")

    # Scans recursively for raw MP3s
    audio_files = sorted(list(audio_dir.rglob("*.mp3")))

    if not audio_files:
        print(f"Error: No MP3 files found in '{audio_dir}'.")
        return

    if args.test_run:
        print("--- TEST RUN: Processing only the first file found ---")
        audio_files = audio_files[:1]

    cooldown_seconds = 180
    prompt_context = VOCAB_PROMPTS[args.context]

    print(f"Found {len(audio_files)} files to process.", flush=True)
    print(f"Using Context: {args.context.upper()}", flush=True)

    for index, audio_path in enumerate(audio_files):
        # Mirror subfolder structure relative to input directory
        relative_path = audio_path.relative_to(audio_dir)
        output_path = output_dir / relative_path.with_suffix(".md")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            continue

        print(
            f"\n[{index + 1}/{len(audio_files)}] STARTING: {audio_path.name}",
            flush=True,
        )

        result: dict[str, Any] = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
            initial_prompt=prompt_context,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
            word_timestamps=False,
        )

        formatted_transcript = ""
        current_paragraph = ""
        paragraph_start_time = None
        tail_history = (
            ""  # Short history for contiguous loop filtering across paragraph breaks
        )

        for segment in result["segments"]:
            start_time = segment["start"]
            end_time = segment["end"]
            text = segment["text"]

            # --- Dynamic Hallucination Filter ---
            skip_segment = False

            # 1. Basic Cleaning & Punctuation Spam
            # 1a. Punctuation Spam (e.g. "......")
            if re.search(r"[.,!?\-_]{6,}", text):
                skip_segment = True

            # 1b. Character Spam (e.g. "aaaaaa" or "年年年年")
            if not skip_segment:
                if re.search(r"([^\s])\1{9,}", text):
                    skip_segment = True

            # 1c. Compress excessive whitespace gaps and strip CJK hallucinations (e.g. 如此)
            if not skip_segment:
                text = re.sub(r"\s{2,}", " ", text).strip()
                # Remove CJK characters (hallucinations like "如此") while preserving English/Pali
                text = re.sub(
                    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\uFAFF\uFF66-\uFF9F]+",
                    "",
                    text,
                )
                if not text or "\x00" in text:
                    skip_segment = True

            # 2. Context-Aware Loops (Word, Phrase, and Cross-Segment)
            if not skip_segment:
                # Clean punctuation for robust matching
                clean_text = re.sub(r"[^\w\s]", " ", text.lower())
                clean_text = re.sub(r"\s+", " ", clean_text).strip()

                clean_history = re.sub(r"[^\w\s]", " ", tail_history.lower())
                clean_history = re.sub(r"\s+", " ", clean_history).strip()

                # Combine history and current text for cross-segment regex check
                combined_text = (clean_history + " " + clean_text).strip()

                # 2a. Punctuation-agnostic Word Loops (NOW CROSS-SEGMENT)
                # Check for 4+ repetitions of a single word in the combined context
                match = re.search(
                    r"\b(\w+)(?:\s+\1){3,}\b", combined_text, re.IGNORECASE
                )
                if match:
                    word = match.group(1).lower()
                    # Whitelist for common fillers: Allow 5, filter 6+
                    if word in [
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
                    ]:
                        if re.search(
                            r"\b(\w+)(?:\s+\1){5,}\b", combined_text, re.IGNORECASE
                        ):
                            skip_segment = True
                    else:
                        skip_segment = True

                # 2b. Context-Aware Phrase Loops (Existing Logic)
                if not skip_segment:
                    if len(clean_text) >= 10 and clean_text in clean_history:
                        skip_segment = True
                    elif clean_text:
                        # 1. Any short phrase (5+ chars) repeated 3+ times
                        if re.search(r"\b(.{5,}?)( \1){2,}", combined_text):
                            skip_segment = True
                        # 2. Any long phrase (15+ chars) repeated 2+ times
                        elif re.search(r"\b(.{15,}?)( \1){1,}", combined_text):
                            skip_segment = True
                        # 3. Any long non-spaced string (30+ chars) repeating once (e.g. CJK spam)
                        elif re.search(r"(.{30,})\1{1,}", text):
                            skip_segment = True

            # 3. Catches low-entropy character spam
            if not skip_segment:
                if len(text) > 20 and len(set(text)) < 5:
                    skip_segment = True

            # 4. Drop suspiciously short, isolated segments (expanded silence hallucinations)
            if not skip_segment:
                if len(text) < 15 and text.lower().strip(".!?,\"' ") in [
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
                ]:
                    skip_segment = True

            if not skip_segment:
                if paragraph_start_time is None:
                    paragraph_start_time = start_time
                current_paragraph += text + " "
                tail_history += text + " "
                # Keep history manageable (last ~150 chars) - strictly for immediate tail matching
                if len(tail_history) > 150:
                    tail_history = tail_history[-150:]
                is_terminal = text.endswith((".", "?", "!", "”", '"'))
            else:
                # If we skipped the segment, evaluate is_terminal based on the existing paragraph
                is_terminal = current_paragraph.strip().endswith(
                    (".", "?", "!", "”", '"')
                )

            # --- Syntactic Chunking Logic ---
            # Wait for both chunk_seconds seconds to pass AND a logical sentence termination
            # OR force a flush after chunk_seconds * 1.5 seconds regardless of punctuation
            if paragraph_start_time is not None:
                is_over_time = end_time - paragraph_start_time >= chunk_seconds
                is_force_flush = end_time - paragraph_start_time >= chunk_seconds * 1.5

                if (is_over_time and is_terminal) or is_force_flush:
                    timestamp_mins = paragraph_start_time / 60.0
                    formatted_transcript += (
                        f"[{timestamp_mins:.1f}] {current_paragraph.strip()}\n\n"
                    )
                    current_paragraph = ""
                    paragraph_start_time = None

        # Flush remainder
        if current_paragraph and paragraph_start_time is not None:
            timestamp_mins = paragraph_start_time / 60.0
            formatted_transcript += (
                f"[{timestamp_mins:.1f}] {current_paragraph.strip()}\n\n"
            )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(formatted_transcript.strip())

        print(f"DONE: {audio_path.name} -> {output_path.name}", flush=True)

        if index < len(audio_files) - 1:
            print(
                f"Thermal pacing: Sleeping for {cooldown_seconds} seconds...",
                flush=True,
            )
            time.sleep(cooldown_seconds)

    print(f"\nBatch processing complete. See {output_dir}", flush=True)


if __name__ == "__main__":
    main()
