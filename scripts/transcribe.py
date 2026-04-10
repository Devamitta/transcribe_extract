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
    args = parser.parse_args()

    audio_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Scans for raw MP3s directly
    audio_files = sorted([f for f in audio_dir.glob("*.mp3") if f.parent == audio_dir])

    if not audio_files:
        print(f"Error: No MP3 files found in '{audio_dir}'.")
        return

    cooldown_seconds = 180
    prompt_context = VOCAB_PROMPTS[args.context]

    print(f"Found {len(audio_files)} files to process.")
    print(f"Using Context: {args.context.upper()}")

    for index, audio_path in enumerate(audio_files):
        output_path = output_dir / audio_path.with_suffix(".md").name

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
            text = segment["text"].strip()

            # --- Dynamic Hallucination Filter ---
            if not text or "" in text:
                continue
            # Catches repetitive loops (e.g., "word word word word")
            if re.search(r"\b(\w+)( \1){3,}\b", text, re.IGNORECASE):
                continue
            # Catches low-entropy character spam
            if len(text) > 20 and len(set(text)) < 5:
                continue

            if paragraph_start_time is None:
                paragraph_start_time = start_time

            current_paragraph += text + " "

            # --- Syntactic Chunking Logic ---
            # Wait for both 60 seconds to pass AND a logical sentence termination
            is_terminal = text.endswith((".", "?", "!", "”", '"'))
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
