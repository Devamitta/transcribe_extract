import mlx_whisper
from pathlib import Path
import time
from typing import Any
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio files using MLX Whisper."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="audio",
        help="Directory containing MP3 files to transcribe (default: audio)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/transcribed",
        help="Directory to save transcription markdown files (default: output/transcribed)",
    )
    args = parser.parse_args()

    # Define paths
    audio_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all MP3 files in audio_dir but exclude subdirectories
    audio_files = sorted([f for f in audio_dir.glob("*.mp3") if f.parent == audio_dir])

    if not audio_files:
        print(f"Error: No MP3 files found in the '{audio_dir}' directory.")
        return

    # Set thermal cooldown in seconds (adjust this based on your preference)
    cooldown_seconds = 180

    print(f"Found {len(audio_files)} files to process.")

    for index, audio_path in enumerate(audio_files):
        # Construct output path (e.g., output/talk1.md)
        output_path = output_dir / audio_path.with_suffix(".md").name

        # Prevent overwriting and allow resuming if interrupted
        if output_path.exists():
            print(f"Skipping '{audio_path.name}' (already exists).")
            continue

        print(f"[{index + 1}/{len(audio_files)}] Transcribing: {audio_path.name}")

        # Execute transcription
        result: dict[str, Any] = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
            initial_prompt="Dhamma, Sangha, Buddha, kamma, nibbāna, saṃsāra, dukkha, samudaya, nirodha, magga, ariya, aṭṭhaṅgika, sammā, diṭṭhi, saṅkappa, vācā, kammanta, ājīva, vāyāma, sati, samādhi, bhāvanā, samatha, vipassanā, jhāna, vitakka, vicāra, pīti, sukha, ekaggatā, nimitta, upacāra, appanā, satipaṭṭhāna, ānāpānasati, mettā, karuṇā, muditā, upekkhā, brahmavihāra, rupa, vedanā, saññā, saṅkhāra, viññāṇa, khandha, kilesa, āsava, nīvaraṇa, lobha, dosa, moha, rāga, paṭigha, māna, avijjā, taṇhā, upādāna, anicca, anattā, suññatā, tilakkhaṇa, paṭiccasamuppāda, idappaccayatā, sīla, vinaya, pāṭimokkha, bhikkhu, bhikkhunī, upāsaka, upāsikā, dāna, puñña, pāramī, adhiṭṭhāna, bhante, āyasmā, thera, mahāthera, tathāgata, arahant, anāgāmī, sakadāgāmī, sotāpanna, sutta, abhidhamma, nikāya, āgama, pāli, vīriya, khantī, sacca, paññā, saddhā, hiri, ottappa, bojjhaṅga, indriya, bala, padhāna, upādāya, āyatana.",
        )

        # Save output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result["text"].strip())

        print(f"Saved: {output_path.name}")

        # Apply thermal mitigation pause (except after the final file)
        if index < len(audio_files) - 1:
            print(f"Thermal pacing: Sleeping for {cooldown_seconds} seconds...")
            time.sleep(cooldown_seconds)

    print("Batch processing complete.")


if __name__ == "__main__":
    main()
