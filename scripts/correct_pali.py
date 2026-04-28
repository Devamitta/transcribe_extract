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

from tools.pali import get_pali_system_instruction, chunk_text_no_overlap
from tools.provider import TEST_MODE, generate_content, get_working_key


def correct_pali_transcription(chunk: str, file_path: Path) -> str:
    system_instruction = get_pali_system_instruction(file_path)
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
                    result = correct_pali_transcription(chunks[i], file_path)
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
