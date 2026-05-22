#!/usr/bin/env python3
"""Transcribes MP3 audio files to markdown using MLX Whisper with context-specific Pali vocabulary prompts."""

import argparse
import re
import time
from pathlib import Path
from typing import Any

import mlx_whisper

from tools.glossary import DHAMMA, SANGHA, VINAYA
from tools.printer import printer as pr

VOCAB_PROMPTS = {
    "sangha": f"Buddhist Saṅgha discussion. Pali terms: {', '.join(SANGHA)}",
    "dhamma": f"Buddhist Dhamma class. Pali terms: {', '.join(DHAMMA)}",
    "vinaya": f"Buddhist Vinaya class. Pali terms: {', '.join(VINAYA)}",
    "interview": f"Buddhist meditation interview. Pali terms: {', '.join(DHAMMA)}",
    "russian": "Буддийская лекция о Дхамме. Pali terms: Nibbāna, Satipaṭṭhāna, Dhamma, Saṅgha",
}

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe raw audio files using MLX Whisper with context-specific Pali glossaries."
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=["ru", "en"],
        help="Language (ru|en); resolves input/output dirs to output/audio/<folder> and output/transcribed/<folder>.",
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder name override (used with --lang to override the default lang folder).",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Explicit input directory (overrides --lang/--folder; defaults to audio/ when neither is given).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Explicit output directory (overrides all derivation).",
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

    if args.input_dir:
        audio_dir = Path(args.input_dir)
        if args.output_dir:
            output_dir = Path(args.output_dir)
        elif audio_dir.is_relative_to("audio"):
            output_dir = Path("output/transcribed") / audio_dir.relative_to("audio")
        else:
            output_dir = Path("output/transcribed")
    elif args.lang:
        lang_folder = args.folder or LANG_TO_FOLDER[args.lang]
        audio_dir = Path("output/audio") / lang_folder
        output_dir = (
            Path(args.output_dir)
            if args.output_dir
            else Path("output/transcribed") / lang_folder
        )
    else:
        audio_dir = Path("audio")
        output_dir = (
            Path(args.output_dir) if args.output_dir else Path("output/transcribed")
        )

    # Scans recursively for raw MP3s
    audio_files = sorted(list(audio_dir.rglob("*.mp3")))

    if not audio_files:
        pr.no(f"No MP3 files found in '{audio_dir}'.")
        return

    if args.test_run:
        pr.amber("TEST RUN: processing only the first file found.")
        audio_files = audio_files[:1]

    # Filter to only files that need transcription before loading the model
    pending = [
        f
        for f in audio_files
        if not (output_dir / f.relative_to(audio_dir).with_suffix(".md")).exists()
    ]
    if not pending:
        pr.yes(f"All {len(audio_files)} transcripts up to date — nothing to do.")
        return
    audio_files = pending

    COOLDOWN_RATIO = 0.30
    MIN_COOLDOWN = 10
    MAX_COOLDOWN = 180
    prompt_context = VOCAB_PROMPTS[args.context]

    pr.green(
        f"Transcribing {len(audio_files)} file(s) — context: {args.context.upper()}"
    )

    for index, audio_path in enumerate(audio_files):
        # Mirror subfolder structure relative to input directory
        relative_path = audio_path.relative_to(audio_dir)
        output_path = output_dir / relative_path.with_suffix(".md")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pr.green(f"[{index + 1}/{len(audio_files)}] {audio_path.name}")

        transcribe_start = time.time()
        pr.bip()
        result: dict[str, Any] = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
            initial_prompt=prompt_context,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
            word_timestamps=False,
        )
        transcribe_elapsed = time.time() - transcribe_start

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

        pr.yes(f"{audio_path.name} → {output_path.name}")

        if index < len(audio_files) - 1:
            cooldown = int(
                max(
                    MIN_COOLDOWN, min(MAX_COOLDOWN, transcribe_elapsed * COOLDOWN_RATIO)
                )
            )
            pr.amber(
                f"Thermal pacing: {transcribe_elapsed:.0f}s work → {cooldown}s cooldown"
            )
            time.sleep(cooldown)

    pr.green(f"Batch complete. Output: {output_dir}")


if __name__ == "__main__":
    main()
