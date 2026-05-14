#!/usr/bin/env python3
"""Extracts core Dhamma teachings from corrected transcripts into structured Q&A format with Pāli topic tags."""

import argparse
import concurrent.futures
import time
from pathlib import Path

from tools import printer as _p
from tools.extract import EXTRACT_SYSTEM_INSTRUCTION as SYSTEM_INSTRUCTION, chunk_text
from tools.provider import (
    build_cacheable_contents,
    generate_with_timeout,
    get_working_key,
)
from tools.incremental import finalize_temp, get_temp_path, load_temp, save_temp

pr = _p.printer


def extract_dhamma_points(text: str) -> str:
    return generate_with_timeout(
        contents=build_cacheable_contents(text),
        system_instruction=SYSTEM_INSTRUCTION,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Dhamma teachings from corrected transcripts."
    )
    parser.add_argument("file", nargs="?", help="Specific file to process")
    parser.add_argument(
        "--folder", help="Process all files in this subfolder (e.g. interview)"
    )
    parser.add_argument("--limit", type=int, help="Limit to first N unprocessed files")

    # --test / -t are handled by the provider module via sys.argv; ignore them here
    args, _ = parser.parse_known_args()

    input_dir = Path("output/corrected_pali")
    output_dir = Path("output/extracted")
    output_dir.mkdir(exist_ok=True)

    if not get_working_key():
        pr.red("All API keys failed. Exiting.")
        return

    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute() and not file_path.exists():
            file_path = input_dir / args.file
        if not file_path.exists():
            pr.red(f"File not found: {file_path}")
            return
        md_files = [file_path]
    elif args.folder:
        folder_path = input_dir / args.folder
        if not folder_path.exists():
            pr.red(f"Folder not found: {folder_path}")
            return
        md_files = sorted(folder_path.rglob("*.md"), key=lambda p: p.name.lower())
    else:
        md_files = sorted(input_dir.rglob("*.md"), key=lambda p: p.name.lower())

    if not md_files:
        pr.amber("No .md files found.")
        return

    queue: list[tuple[Path, Path]] = []
    skipped = 0
    for fp in md_files:
        try:
            rel = fp.relative_to(input_dir)
            out_path = output_dir / rel
        except ValueError:
            out_path = output_dir / fp.name

        if out_path.exists():
            pr.amber(f"[SKIP] {fp.name}")
            skipped += 1
        else:
            queue.append((fp, out_path))

    if skipped:
        pr.green(f"{skipped} already extracted, {len(queue)} to process")

    if args.limit and len(queue) > args.limit:
        pr.green(f"Limiting to first {args.limit} files (--limit).")
        queue = queue[: args.limit]

    if not queue:
        pr.green("Nothing to process.")
        return

    pr.green(f"Processing {len(queue)} file(s)")

    for idx, (fp, out_path) in enumerate(queue):
        pr.green(f"Extracting '{fp.name}'...")
        text = fp.read_text(encoding="utf-8")
        chunks = chunk_text(text)

        temp_path = get_temp_path(out_path)
        saved: list[str] = load_temp(temp_path)
        start = len(saved)

        if 0 < start < len(chunks):
            pr.green(f"  Resuming from chunk {start + 1}/{len(chunks)}...")

        for i, chunk in enumerate(chunks):
            if i < start:
                continue
            pr.green(f"  Chunk {i + 1}/{len(chunks)}...")
            try:
                result = extract_dhamma_points(chunk)
                saved.append("" if "NO_POINTS" in result.strip() else result.strip())
            except concurrent.futures.TimeoutError:
                pr.amber(f"  Chunk {i + 1} timed out — skipping.")
                saved.append("")
            except Exception as e:
                pr.amber(f"  Chunk {i + 1} failed: {e}")
                saved.append("")
            save_temp(temp_path, saved)

        all_points = [p for p in saved if p]
        if all_points:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("\n\n".join(all_points), encoding="utf-8")
            pr.yes(f"saved → {out_path}")
        else:
            pr.no(f"no Dhamma points found in '{fp.name}'")
        
        finalize_temp(temp_path)

        if idx < len(queue) - 1:
            pr.green("Waiting 5s...")
            time.sleep(5)


if __name__ == "__main__":
    main()
