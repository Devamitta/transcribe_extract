#!/usr/bin/env python3
"""Transcribes MP3 audio files to markdown using MLX Whisper with context-specific Pali vocabulary prompts."""

import mlx_whisper
from pathlib import Path
import time
from typing import Any
import argparse
import re

VOCAB_PROMPTS = {
    "sangha": "Buddhist Saṅgha discussion. Pali terms: Saṅgha, Dhamma, kamma, bhikkhu, sāmaṇera, upāsaka, vihāra, dāna, sīla, bhante, āyasmā, thera, mahāthera, puñña, vinaya, pāṭimokkha, uposatha, vassa, kaṭhina, nissaya, pavāraṇā, kappiya, kamma, apalokana, ñatti, kammavācā, sīmā, kuṭi, piṇḍacāra, cīvara, dāna, upajjhāya, ācariya, saddhā.",
    "dhamma": "Buddhist Dhamma class. Pali terms: Saṅgha, Dhamma, sutta, nikāya, āgama, abhidhamma, pāli, khandha, rupa, vedanā, saññā, saṅkhāra, viññāṇa, anicca, anatta, dukkha, paṭiccasamuppāda, avijjā, taṇhā, upādāna, kamma, nibbāna, magga, ariya, sacca, kilesa, āsava, nīvaraṇa, lobha, dosa, moha, rāga, māna, bhava, jāti, saṃsāra, brahmavihāra, mettā, karuṇā, muditā, upekkhā, pāramī, puñña, kusala, akusala, paññā, vimutti.",
    "vinaya": "Buddhist Vinaya class. Pali terms: Saṅgha, Dhamma, Vinaya, pāṭimokkha, bhikkhu, bhikkhunī, pārājika, saṅghādisesa, aniyata, nissaggiya, pācittiya, pāṭidesanīya, sekhiya, adhikaraṇasamatha, apatti, thullaccaya, dukkaṭa, dubbhāsita, nissaya, ācariya, upajjhāya, vassa, pavāraṇā, cīvara, piṇḍacāra, kappiya, kamma, sīmā, uposatha, antaravāsaka, uttarāsaṅga, saṅghāṭi, patta, vikappana, dāna, desanā, upasampadā, pabbajjā, sikkhamānā.",
    "interview": "Buddhist meditation interview. Pali terms: Saṅgha, Dhamma, satipaṭṭhāna, ānāpānasati, sati, samādhi, bhāvanā, samatha, vipassanā, jhāna, vitakka, vicāra, pīti, sukha, ekaggatā, nimitta, nīvaraṇa, lobha, dosa, moha, kilesa, mettā, vīriya, khantī, saddhā, paññā, hiri, ottappa, bojjhaṅga, indriya, bala, padhāna, upekkhā, rūpa, arūpa, asubha, maraṇassati, anicca, dukkha, anatta, rāga, thīnamiddha, uddhacca, kukkucca, vicikicchā, passaddhi, sampajañña, kusala.",
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
        default="output/transcribed",
        help="Directory to save transcription markdown files",
    )
    parser.add_argument(
        "--context",
        type=str,
        choices=["sangha", "dhamma", "vinaya", "interview"],
        default="interview",
        help="Select the Pali vocabulary context.",
    )
    parser.add_argument(
        "--test-run",
        action="store_true",
        help="If active, only transcribe the first file found (for testing).",
    )
    args = parser.parse_args()

    audio_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

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

    print(f"Found {len(audio_files)} files to process.")
    print(f"Using Context: {args.context.upper()}")

    for index, audio_path in enumerate(audio_files):
        # Mirror subfolder structure relative to input directory
        relative_path = audio_path.relative_to(audio_dir)
        output_path = output_dir / relative_path.with_suffix(".md")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            print(f"Skipping '{audio_path.name}' (already exists).")
            continue

        print(f"[{index + 1}/{len(audio_files)}] Transcribing: {audio_path.name}")

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

        for segment in result["segments"]:
            start_time = segment["start"]
            end_time = segment["end"]
            text = segment["text"]

            # --- Dynamic Hallucination Filter ---
            skip_segment = False

            # 1. Compress excessive whitespace gaps
            text = re.sub(r"\s{2,}", " ", text).strip()

            if not text or "\x00" in text:
                skip_segment = True

            # 2. Punctuation-agnostic Word Loops (4+ repetitions)
            # Strip punctuation for word loop check (e.g., "Valuable. Valuable. Valuable.")
            if not skip_segment:
                clean_text_only = re.sub(r"[^\w\s]", "", text).strip()
                if re.search(r"\b(\w+)( \1){3,}\b", clean_text_only, re.IGNORECASE):
                    skip_segment = True

            # 3. Context-Aware Sentence/Phrase Loops
            # Only check if the new text is a substantial repetition of what's already in the paragraph
            if not skip_segment:
                # Clean punctuation for robust matching
                clean_text = re.sub(r"[^\w\s]", " ", text.lower())
                clean_text = re.sub(r"\s+", " ", clean_text).strip()

                clean_para = re.sub(r"[^\w\s]", " ", current_paragraph.lower())
                clean_para = re.sub(r"\s+", " ", clean_para).strip()

                if len(clean_text) > 15 and clean_text in clean_para:
                    skip_segment = True
                elif clean_text:
                    # Check for internal phrase loops
                    # 1. Any short phrase (5+ chars) repeated 3+ times
                    if re.search(r"\b(.{5,}?)( \1){2,}\b", clean_text):
                        skip_segment = True
                    # 2. Any long phrase (15+ chars) repeated 2+ times
                    elif re.search(r"\b(.{15,}?)( \1){1,}\b", clean_text):
                        skip_segment = True

            # 4. Catches low-entropy character spam
            if not skip_segment:
                if len(text) > 20 and len(set(text)) < 5:
                    skip_segment = True

            # 5. Drop suspiciously short, isolated segments (expanded silence hallucinations)
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
                is_terminal = text.endswith((".", "?", "!", "”", '"'))
            else:
                # If we skipped the segment, evaluate is_terminal based on the existing paragraph
                is_terminal = current_paragraph.strip().endswith(
                    (".", "?", "!", "”", '"')
                )

            # --- Syntactic Chunking Logic ---
            # Wait for both 60 seconds to pass AND a logical sentence termination
            if paragraph_start_time is not None:
                if (end_time - paragraph_start_time >= 60.0) and is_terminal:
                    timestamp_mins = paragraph_start_time / 60.0
                    formatted_transcript += (
                        f"[{timestamp_mins:.1f}] {current_paragraph.strip()}\n\n"
                    )
                    current_paragraph = ""
                    paragraph_start_time = None

        # Flush remainder
        if current_paragraph:
            timestamp_mins = paragraph_start_time / 60.0
            formatted_transcript += (
                f"[{timestamp_mins:.1f}] {current_paragraph.strip()}\n\n"
            )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(formatted_transcript.strip())

        print(f"Saved: {output_path.name}")

        if index < len(audio_files) - 1:
            print(f"Thermal pacing: Sleeping for {cooldown_seconds} seconds...")
            time.sleep(cooldown_seconds)

    print("Batch processing complete.")


if __name__ == "__main__":
    main()
