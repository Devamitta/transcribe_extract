#!/usr/bin/env python3
"""Corrects Pāli phonetic spellings in transcribed text using Gemini API and a Pāli glossary."""

import sys
from pathlib import Path
import time

from tools.provider import generate_content, get_working_key, TEST_MODE

PALI_GLOSSARY = (
    "Dhamma, Sangha, Buddha, kamma, nibbāna, saṃsāra, dukkha, samudaya, nirodha, magga, ariya, aṭṭhaṅgika, "
    "sammā, diṭṭhi, saṅkappa, vācā, kammanta, ājīva, vāyāma, sati, samādhi, bhāvanā, samatha, vipassanā, "
    "jhāna, vitakka, vicāra, pīti, sukha, ekaggatā, nimitta, upacāra, appanā, satipaṭṭhāna, ānāpānasati, "
    "mettā, karuṇā, muditā, upekkhā, brahmavihāra, rupa, vedanā, saññā, saṅkhāra, viññāṇa, khandha, kilesa, "
    "āsava, nīvaraṇa, lobha, dosa, moha, rāga, paṭigha, māna, avijjā, taṇhā, upādāna, anicca, anattā, "
    "suññatā, tilakkhaṇa, paṭiccasamuppāda, idappaccayatā, sīla, vinaya, pāṭimokkha, bhikkhu, bhikkhunī, "
    "upāsaka, upāsikā, dāna, puñña, pāramī, adhiṭṭhāna, bhante, āyasmā, thera, mahāthera, tathāgata, arahant, "
    "anāgāmī, sakadāgāmī, sotāpanna, sutta, abhidhamma, nikāya, āgama, pāli, vīriya, khantī, sacca,aññā, "
    "saddhā, hiri, ottappa, bojjhaṅga, indriya, bala, padhāna, upādāya, āyatana."
)


def chunk_text_no_overlap(text: str, chunk_size: int = 2000) -> list[str]:
    words = text.split()
    return [
        " ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)
    ]


def correct_pali_transcription(chunk: str) -> str:
    system_instruction = (
        "You are a strict text correction engine. "
        f"Correct phonetic misspellings: [{PALI_GLOSSARY}]. "
        "Output ONLY corrected text. No markdown."
    )
    return generate_content(
        contents=chunk,
        system_instruction=system_instruction,
    )


def get_completed_chunks(fp: Path, output_dir: Path) -> int:
    status_dir = output_dir / ".status"
    status_dir.mkdir(exist_ok=True)
    sf = status_dir / f"{fp.stem}.status"
    if sf.exists():
        try:
            return int(sf.read_text().strip())
        except ValueError:
            return 0
    return 0


def mark_completed_chunks(fp: Path, output_dir: Path, completed: int) -> None:
    status_dir = output_dir / ".status"
    status_dir.mkdir(exist_ok=True)
    sf = status_dir / f"{fp.stem}.status"
    sf.write_text(str(completed))


def main():
    input_dir = Path("output/transcribed_output")
    output_dir = Path("output/corrected_pali")
    output_dir.mkdir(exist_ok=True)

    if not get_working_key():
        print("All API keys failed. Exiting.")
        return

    # Parse args: optional file (--test flag handled by provider)
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    specific_file = args[0] if args else None

    if specific_file:
        # If it's a full path, use it directly; otherwise look in input_dir
        if Path(specific_file).is_absolute() or Path(specific_file).exists():
            md_files = [Path(specific_file)]
        else:
            md_files = [input_dir / specific_file]
        if not md_files[0].exists():
            print(f"File not found: {md_files[0]}")
            return
    else:
        md_files = list(input_dir.glob("*.md"))
        if not md_files:
            print("No files in 'transcribed_output/'.")
            return

    print(f"Found {len(md_files)} files", flush=True)

    for file_path in md_files:
        final_output = output_dir / file_path.name
        temp_output = output_dir / f".{file_path.name}.tmp"

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text_no_overlap(text)
        total = len(chunks)

        completed = get_completed_chunks(file_path, output_dir)
        start = completed

        if final_output.exists() and completed >= total:
            print(f"Skipping '{file_path.name}', done.")
            continue
        elif completed > 0:
            print(
                f"Resuming '{file_path.name}' from chunk {completed + 1}/{total}",
                flush=True,
            )
        else:
            print(f"Correcting '{file_path.name}'...", flush=True)

        if TEST_MODE:
            total = min(3, total)

        if temp_output.exists():
            corrected = temp_output.read_text().split()
        elif start > 0:
            corrected = final_output.read_text().split()
        else:
            corrected = []
        failed = []

        print(f"  {total - start} chunks to process", flush=True)

        for i in range(start, total):
            print(f"  Chunk {i + 1}/{total}...", flush=True)
            for attempt in range(3):
                try:
                    result = correct_pali_transcription(chunks[i])
                    corrected.append(result.strip())
                    temp_output.write_text(" ".join(corrected))
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"  Failed: {e}", flush=True)
                        failed.append(i + 1)
            time.sleep(2)

        temp_output.write_text(" ".join(corrected))
        if failed:
            mark_completed_chunks(
                file_path, output_dir, start + len(corrected) - len(failed)
            )
            final_output.write_text(" ".join(corrected))
            temp_output.unlink()
            print(f"Saved (partial). Failed: {failed}")
        elif not failed:
            mark_completed_chunks(file_path, output_dir, total)
            final_output.write_text(" ".join(corrected))
            temp_output.unlink()
            print(f"Saved to '{final_output.name}'.")

        print("  Waiting 5s between files...", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
