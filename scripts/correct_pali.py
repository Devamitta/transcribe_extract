#!/usr/bin/env python3
"""Corrects Pāli phonetic spellings in transcribed text using Gemini API and a Pāli glossary."""

import sys
from pathlib import Path
import time

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.glossary import SANGHA, DHAMMA, VINAYA
from tools.provider import generate_content, get_working_key, TEST_MODE

# Combine all lists, deduplicate, and sort
_combined_glossary = sorted(list(set(SANGHA + DHAMMA + VINAYA)))
PALI_GLOSSARY = ", ".join(_combined_glossary)


def chunk_text_no_overlap(text: str, chunk_size: int = 2000) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0
    for p in paragraphs:
        words = len(p.split())
        if current_length + words > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(p)
        current_length += words
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    return chunks


def correct_pali_transcription(chunk: str) -> str:
    system_instruction = (
        "You are a highly constrained text correction engine. Your ONLY job is to fix phonetic misspellings of Pali words found in the provided glossary.\n\n"
        "CRITICAL RULES:\n"
        "1. DO NOT change, remove, or summarize any English words.\n"
        "2. DO NOT add punctuation or change capitalization unless it is to fix a Pali word.\n"
        "3. DO NOT output any conversational text, explanations, or markdown formatting. NEVER START YOUR RESPONSE WITH 'Here is...', 'I have corrected...', 'Sure', or similar AI conversational starters. NEVER USE BACKTICKS (```) to enclose the output.\n"
        "4. ONLY apply corrections if a word in the text sounds phonetically identical or highly similar to a word in the glossary.\n"
        "5. If a word is a valid English word (e.g., 'comma', 'karma', 'sangha' without diacritics), only change it to the Pali equivalent (e.g., 'kamma', 'Saṅgha') if the context clearly implies it.\n"
        "6. COMPOUND WORDS: If a transcribed word sounds like a combination of two or more words from the glossary, combine them using a hyphen (e.g., 'samanasanna' -> 'samaṇa-saññā').\n"
        "7. ENGLISH PLURALS: If a Pali word is pluralized with an English 's' (e.g., 'bhikkhus', 'theras'), KEEP the 's' at the end of the corrected Pali word (e.g., 'bhikkhus', 'theras').\n"
        "8. DO NOT OMIT OR DELETE any part of the text. The length and content (other than Pali corrections) must remain exactly the same as the input.\n\n"
        f"PALI GLOSSARY: [{PALI_GLOSSARY}]\n\n"
        "Output EXACTLY the original text with only the misspelled Pali words corrected."
    )
    return generate_content(
        contents=chunk,
        system_instruction=system_instruction,
    )


def get_completed_chunks(output_file: Path) -> int:
    status_dir = output_file.parent / ".status"
    status_dir.mkdir(exist_ok=True)
    sf = status_dir / f"{output_file.stem}.status"
    if sf.exists():
        try:
            return int(sf.read_text().strip())
        except ValueError:
            return 0
    return 0


def mark_completed_chunks(output_file: Path, completed: int) -> None:
    status_dir = output_file.parent / ".status"
    status_dir.mkdir(exist_ok=True)
    sf = status_dir / f"{output_file.stem}.status"
    sf.write_text(str(completed))


def main():
    input_dir = Path("output/transcribed")
    output_dir = Path("output/corrected_pali")
    output_dir.mkdir(exist_ok=True, parents=True)

    if not get_working_key():
        print("All API keys failed. Exiting.")
        return

    # Parse args: optional file (--test flag handled by provider)
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    specific_file = args[0] if args else None

    if specific_file:
        path = Path(specific_file)
        if not path.is_absolute() and not path.exists():
            path = input_dir / specific_file

        if not path.exists():
            print(f"Path not found: {path}")
            return

        if path.is_dir():
            md_files = sorted(list(path.rglob("*.md")))
        else:
            md_files = [path]

        if not md_files:
            print(f"No .md files found in {path}")
            return
    else:
        # Recursively find all markdown files in input_dir
        md_files = sorted(list(input_dir.rglob("*.md")))
        if not md_files:
            print(f"No files in '{input_dir}'.")
            return

    print(f"Found {len(md_files)} files", flush=True)

    for file_path in md_files:
        # Preserve directory structure relative to input_dir
        try:
            relative_path = file_path.relative_to(input_dir)
            final_output = output_dir / relative_path
        except ValueError:
            # Fallback for files outside input_dir (like specific_file)
            final_output = output_dir / file_path.name

        final_output.parent.mkdir(parents=True, exist_ok=True)
        temp_output = final_output.parent / f".{final_output.name}.tmp"

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text_no_overlap(text)
        total = len(chunks)

        completed = get_completed_chunks(final_output)
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
            corrected = temp_output.read_text().split("\n\n")
            if len(corrected) != start:
                start = len(corrected)
        elif start > 0 and final_output.exists():
            corrected = final_output.read_text().split("\n\n")
        else:
            start = 0
            corrected = []
        failed = []

        print(f"  {total - start} chunks to process", flush=True)

        for i in range(start, total):
            print(f"  Chunk {i + 1}/{total}...", flush=True)
            success = False
            for attempt in range(3):
                try:
                    result = correct_pali_transcription(chunks[i])
                    corrected.append(result.strip())
                    temp_output.write_text("\n\n".join(corrected))
                    success = True
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"  Failed: {e}", flush=True)
                        failed.append(i + 1)
            if not success:
                break
            time.sleep(2)

        if failed:
            mark_completed_chunks(final_output, len(corrected))
            # Leave progress in temp_output, DO NOT write to final_output
            print(f"Saved (partial) to temp file. Failed chunks: {failed}")
        else:
            mark_completed_chunks(final_output, total)
            final_output.write_text("\n\n".join(corrected))
            if temp_output.exists():
                temp_output.unlink()
            print(f"Saved to '{final_output.name}'.")

        print("  Waiting 5s between files...", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
