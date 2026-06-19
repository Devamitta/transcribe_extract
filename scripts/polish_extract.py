#!/usr/bin/env python3
"""Polishes extracted Dhamma transcripts for readability."""

import argparse
import concurrent.futures
import time
from pathlib import Path

from tools import printer as _p
from tools.extract import chunk_text
from tools.polish import (
    POLISH_SYSTEM_INSTRUCTION as SYSTEM_INSTRUCTION,
    POLISH_WORD_TOLERANCE,
    validate_word_count,
)
from tools.provider import (
    build_cacheable_contents,
    generate_with_timeout,
)
from tools.incremental import finalize_temp, get_temp_path, load_temp, save_temp

pr = _p.printer


def polish_text(text: str) -> str:
    """Polishes a single chunk of text."""
    return generate_with_timeout(
        contents=build_cacheable_contents(text),
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
        out_path = mirror_path(fp, input_dir, output_dir)

        if out_path.exists():
            skipped += 1
        else:
            queue.append((fp, out_path))

    if skipped:
        pr.green(f"{skipped} already polished, {len(queue)} to process")

    if args.limit and len(queue) > args.limit:
        pr.green(f"Limiting to first {args.limit} files (--limit).")
        queue = queue[: args.limit]

    if not queue:
        pr.green("Nothing to process.")
        return

    if args.dry_run:
        pr.green(f"Dry run: {len(queue)} file(s) would be processed")
        for fp, out_path in queue:
            pr.green(f"{fp} -> {out_path}")
        pr.summary("skipped", skipped)
        pr.summary("queued", len(queue))
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

        temp_path = get_temp_path(out_path)
        saved: list[str] = load_temp(temp_path)
        start = len(saved)

        if 0 < start < len(chunks):
            pr.green(f"  Resuming from chunk {start + 1}/{len(chunks)}...")

        had_failure = False
        for i, chunk in enumerate(chunks):
            if i < start:
                continue
            if len(chunks) > 1:
                pr.green(f"    Chunk {i + 1}/{len(chunks)}...")
            try:
                result = polish_text(chunk)
                saved.append(result.strip() if result else "")
            except concurrent.futures.TimeoutError:
                pr.amber(f"    Chunk {i + 1} timed out — saving partial.")
                saved.append("")
                had_failure = True
            except Exception as e:
                pr.amber(f"    Chunk {i + 1} failed: {e}")
                saved.append("")
                had_failure = True
            save_temp(temp_path, saved)

            if i < len(chunks) - 1:
                time.sleep(2)

        all_polished = [p for p in saved if p and p != "NO_POINTS"]
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
                pr.amber(f"  [VAL FAIL] Word count out of bounds for {fp.name}")
                failed += 1
        else:
            if had_failure:
                pr.no(f"  nothing to save for '{fp.name}' (all chunks failed)")
            else:
                pr.no(f"  nothing to save for '{fp.name}'")
            failed += 1

        finalize_temp(temp_path)

        if idx < len(queue) - 1:
            pr.green("Waiting 5s...")
            time.sleep(5)

    pr.summary("total", len(queue))
    pr.summary("succeeded", succeeded)
    pr.summary("failed", failed)
    pr.summary("skipped", skipped + empty)
    pr.summary("input words", total_words)


if __name__ == "__main__":
    main()
