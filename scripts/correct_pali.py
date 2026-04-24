#!/usr/bin/env python3
"""Corrects Pāli phonetic spellings in transcribed text using Gemini API and a Pāli glossary.

Usage examples:
    # Process all files in output/transcribed/
    uv run python scripts/correct_pali.py

    # Process only files in output/transcribed/sangha/
    uv run python scripts/correct_pali.py sangha

    # Process a specific file
    uv run python scripts/correct_pali.py interview/talk.md
"""

import json
import re
import sys
import time
from pathlib import Path

from tools.glossary import DHAMMA, EXTENDED_TERMS, MONASTICS, PLACES, SANGHA, VINAYA
from tools.provider import TEST_MODE, generate_content, get_working_key

# Combine all lists, deduplicate, and sort
_combined_glossary = sorted(
    list(set(SANGHA + DHAMMA + VINAYA + EXTENDED_TERMS + MONASTICS + PLACES))
)
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
        "You are an expert Pali proofreader. Your task is to identify phonetic and semantic misspellings of Pali words, Buddhist terms, or monastery names in a provided text and suggest corrections based on a glossary.\n\n"
        "INSTRUCTIONS:\n"
        "1. Analyze the input text for any words or phrases that sound like or are semantically related to terms in the PALI GLOSSARY.\n"
        "2. STRICT CONTEXT CHECK: Only correct a word if the surrounding context clearly indicates a Buddhist or Pali concept was intended.\n"
        "3. WATCH CAPITALIZATION: Be highly suspicious of capitalized English names (e.g., 'Sutter', 'Mach', 'Vinyan') if the context points to a Pali term. Speech-to-text software frequently capitalizes Pali words by mistake.\n"
        "4. IGNORE ACRONYMS: Do NOT correct ALL CAPS acronyms (e.g., 'SPS', 'MBS') UNLESS they are in the glossary (e.g., 'SBS').\n"
        "5. MULTI-WORD BRIDGING: Whisper often inserts spaces into the middle of Pali words. You MUST identify two-word or three-word sequences that together form a single glossary term.\n"
        "   Example: 'Viragadham Mikam' -> 'Virāgadhammikaṁ', 'Ios Mokiti' -> 'āyasmā Kittisobhana'.\n"
        "6. CONSISTENCY: If you identify a correction, scan the rest of the text for phonetic variations of that same term (e.g., if you fix 'Raghadamica', also fix 'Ergadamica').\n"
        "7. SEMANTIC HALLUCINATIONS: Watch for 'Deep Hallucinations' where the transcriber replaces complex terms with common English phrases.\n"
        "   Examples:\n"
        "   - 'Norway for far' -> 'Noble Eightfold Path'\n"
        "   - 'Marginal Triad' -> 'Majjhima Nikāya'\n"
        "   - 'put up' -> 'patta'\n"
        "   - 'Logan needed' -> 'lokavidū'\n"
        "   - 'the ergonomic big group' -> 'the Virāgadhammika Bhikkhu'\n"
        "   - 'share the down' -> 'share the Dhamma'\n"
        "8. MONASTIC NAMES & TITLES: Correct phonetic misspellings of names and titles.\n"
        "   - Examples: 'Bandiaga Jitta' -> 'Bhante Aggacitta', 'Kusavachara Bikku' -> 'Kusalacāra Bhikkhu'.\n"
        "   - SHORTENED NAMES: Monastic names ending in '-dhammika' are often shortened (e.g., 'Virāga' -> 'Virāgadhammika').\n"
        "9. Output ONLY a valid JSON array of objects with 'original' and 'corrected' keys. No other text.\n"
        "10. ENGLISH BUDDHIST TERMS: Watch for phonetic mistranslations of common English Buddhist words (e.g., 'senior moms' -> 'senior monks', 'non' -> 'nun').\n"
        "11. EXTREME PHONETIC DISTORTIONS: Whisper severely distorts foreign place names. Look for extreme phonetic matches (e.g., 'Waddenwood-Pupon' -> 'Wat Nong Pah Pong').\n"
        f"PALI GLOSSARY: [{PALI_GLOSSARY}]"
    )
    result = generate_content(
        contents=chunk,
        system_instruction=system_instruction,
    )

    try:
        # Clean and parse JSON
        json_str = result.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:].strip()
        if json_str.endswith("```"):
            json_str = json_str[:-3].strip()

        corrections = json.loads(json_str)
        
        # Apply replacements to the original chunk using regex for whole words
        corrected_chunk = chunk
        for item in corrections:
            # Ensure the item is a dictionary and has the required keys before proceeding
            if (
                not isinstance(item, dict)
                or "original" not in item
                or "corrected" not in item
            ):
                continue

            orig = str(item["original"])
            corr = str(item["corrected"])

            # Use regex to replace whole words only, case-insensitive for the search
            pattern = re.compile(rf"\b{re.escape(orig)}\b", re.IGNORECASE)
            corrected_chunk = pattern.sub(corr, corrected_chunk)

        return corrected_chunk

    except (json.JSONDecodeError, Exception) as e:
        # Fallback: if JSON fails or replacement fails, return the original uncorrupted chunk
        print(
            f"  Warning: JSON correction failed for chunk: {e}. Skipping corrections."
        )
        return chunk


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

    print(f"Found {len(md_files)} files:", flush=True)
    for f in md_files:
        print(f" - {f.name}", flush=True)

    for idx, file_path in enumerate(md_files):
        remaining = len(md_files) - idx
        print(
            f"\n[{remaining} files left] Processing '{file_path.name}'...", flush=True
        )

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
            print("  Skipping (already done).", flush=True)
            continue
        elif completed > 0:
            print(
                f"  Resuming from chunk {completed + 1}/{total}",
                flush=True,
            )
        else:
            print("  Starting correction...", flush=True)

        if TEST_MODE:
            total = min(3, total)

        if temp_output.exists():
            try:
                corrected = json.loads(temp_output.read_text())
                if len(corrected) != start:
                    start = len(corrected)
            except json.JSONDecodeError:
                # Fallback if temp file is corrupted
                start = 0
                corrected = []
        elif start > 0 and final_output.exists():
            # If we have a final file but need to resume, we'd need to re-chunk it
            # which is complex. For now, let's just restart if no temp file.
            start = 0
            corrected = []
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
                    temp_output.write_text(json.dumps(corrected))
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
            print(f"Saved to '{final_output}'.")

        print("  Waiting 5s between files...", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
