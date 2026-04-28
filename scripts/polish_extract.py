#!/usr/bin/env python3
"""Polishes extracted Dhamma transcripts for readability."""

import argparse
import time
from pathlib import Path

from tools import printer as _p
from tools.extract import chunk_text
from tools.polish import (
    POLISH_SYSTEM_INSTRUCTION as SYSTEM_INSTRUCTION,
    POLISH_WORD_TOLERANCE,
    validate_word_count,
)
from tools.provider import generate_content, get_working_key

pr = _p.printer


def polish_text(text: str) -> str:
    """Polishes a single chunk of text."""
    return generate_content(
        contents=text,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.1,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the polish script."""
    parser = argparse.ArgumentParser(
        description="Polish extracted transcripts for readability."
    )
    parser.add_argument("file", nargs="?", help="Specific file to process")
    parser.add_argument(
        "--folder", help="Process all files in this subfolder of output/extracted"
    )
    parser.add_argument("--limit", type=int, help="Limit to first N unprocessed files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without writing output files",
    )

    return parser


def mirror_path(input_file: Path, input_base: Path, output_base: Path) -> Path:
    """Mirror an extracted file path into the polished output tree."""
    try:
        relative_path = input_file.relative_to(input_base)
    except ValueError:
        return output_base / input_file.name

    return output_base / relative_path


def build_chunks(text: str) -> list[str]:
    """Chunk large files without overlap to avoid duplicate polished output."""
    if len(text.split()) < 2000:
        return [text]

    return chunk_text(text, chunk_size=3000, overlap=0)


def main() -> None:
    parser = build_parser()

    # --test / -t are handled by tools.provider
    args, _ = parser.parse_known_args()

    input_dir = Path("output/extracted")
    output_dir = Path("output/polished")
    output_dir.mkdir(exist_ok=True)

    # File discovery
    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute() and not file_path.exists():
            file_path = input_dir / args.file
        if not file_path.exists():
            pr.error(f"File not found: {file_path}")
            return
        md_files = [file_path]
    elif args.folder:
        folder_path = input_dir / args.folder
        if not folder_path.exists():
            pr.error(f"Folder not found: {folder_path}")
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
        out_path = mirror_path(fp, input_dir, output_dir)

        if out_path.exists():
            skipped += 1
        else:
            queue.append((fp, out_path))

    if skipped:
        pr.info(f"{skipped} already polished, {len(queue)} to process")

    if args.limit and len(queue) > args.limit:
        pr.info(f"Limiting to first {args.limit} files (--limit).")
        queue = queue[: args.limit]

    if not queue:
        pr.info("Nothing to process.")
        return

    if args.dry_run:
        pr.green(f"Dry run: {len(queue)} file(s) would be processed")
        for fp, out_path in queue:
            pr.info(f"{fp} -> {out_path}")
        pr.summary("skipped", skipped)
        pr.summary("queued", len(queue))
        return

    if not get_working_key():
        pr.error("No working API key found.")
        return

    pr.green(f"Processing {len(queue)} file(s)")

    succeeded = 0
    failed = 0
    empty = 0
    total_words = 0

    for idx, (fp, out_path) in enumerate(queue):
        pr.green(f"Polishing '{fp.name}'...")
        text = fp.read_text(encoding="utf-8")
        if not text.strip():
            pr.amber(f"  [SKIP] '{fp.name}' is empty")
            empty += 1
            continue

        total_words += len(text.split())
        chunks = build_chunks(text)

        all_polished = []
        failed_chunk = False

        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                pr.info(f"    Chunk {i + 1}/{len(chunks)}...")
            try:
                result = polish_text(chunk)
                if result and result.strip() != "NO_POINTS":
                    all_polished.append(result.strip())
                elif result.strip() == "NO_POINTS":
                    all_polished.append("NO_POINTS")
            except Exception as e:
                pr.warning(f"    Chunk {i + 1} failed: {e}")
                failed_chunk = True
                break

            if i < len(chunks) - 1:
                time.sleep(2)

        if failed_chunk:
            pr.no(f"  Failed polishing '{fp.name}' due to chunk failure")
            failed += 1
            continue

        if all_polished:
            polished_text = "\n\n".join(all_polished)
            if validate_word_count(
                text, polished_text, tolerance=POLISH_WORD_TOLERANCE
            ):
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(polished_text, encoding="utf-8")
                pr.yes(f"  saved → {out_path}")
                succeeded += 1
            else:
                pr.warning(f"  [VAL FAIL] Word count out of bounds for {fp.name}")
                failed += 1
        else:
            pr.no(f"  nothing to save for '{fp.name}'")
            failed += 1

        if idx < len(queue) - 1:
            pr.info("Waiting 5s...")
            time.sleep(5)

    pr.summary("total", len(queue))
    pr.summary("succeeded", succeeded)
    pr.summary("failed", failed)
    pr.summary("skipped", skipped + empty)
    pr.summary("input words", total_words)


if __name__ == "__main__":
    main()
