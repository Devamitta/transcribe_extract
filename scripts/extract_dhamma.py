#!/usr/bin/env python3
"""Extracts core Dhamma teachings from corrected transcripts into structured Q&A format with Pāli topic tags."""

import sys
from pathlib import Path
import time


from tools.extract import EXTRACT_SYSTEM_INSTRUCTION as SYSTEM_INSTRUCTION, chunk_text
from tools.provider import generate_content, get_working_key


def extract_dhamma_points(text: str) -> str:
    return generate_content(
        contents=text,
        system_instruction=SYSTEM_INSTRUCTION,
    )


def main():
    input_dir = Path("output/corrected_pali")
    output_dir = Path("output/extracted")
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
            print("No files found in 'corrected_pali/'. Run correct_pali.py first.")
            return

    print(f"Found {len(md_files)} files", flush=True)

    for file_path in md_files:
        final_output_path = output_dir / file_path.name
        if final_output_path.exists():
            print(f"Skipping '{file_path.name}', already extracted.")
            continue

        print(f"Extracting points from '{file_path.name}'...")
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text(text)
        all_points = []

        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i + 1}/{len(chunks)}...", flush=True)
            try:
                result = extract_dhamma_points(chunk)
                if "NO_POINTS" not in result.strip():
                    all_points.append(result.strip())
            except Exception as e:
                print(f"    Failed on chunk {i + 1}: {e}")

        if all_points:
            with open(final_output_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(all_points))
            print(f"Extraction saved to '{final_output_path.name}'.\n")
        else:
            print(f"No Dhamma points found in '{file_path.name}'.\n")

        print("  Waiting 5s between files...", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
