#!/usr/bin/env python3
"""Polishes extracted Dhamma transcripts for readability."""

import argparse
from pathlib import Path

from tools.chunk_runner import RunnerConfig, mirror_output_path, run
from tools.chunking import chunk_text_by_paragraph
from tools.polish import (
    POLISH_SYSTEM_INSTRUCTION as SYSTEM_INSTRUCTION,
    POLISH_WORD_TOLERANCE,
    validate_word_count,
)
from tools.provider import (
    build_cacheable_contents,
    generate_with_timeout,
)

INTER_CALL_PACING_SECONDS = 2.0


def polish_text(text: str, _file_path: Path | None = None) -> str:
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
    return mirror_output_path(input_file, input_base, output_base)


def build_chunks(text: str) -> list[str]:
    """Chunk extracted markdown on paragraph boundaries."""
    return chunk_text_by_paragraph(text, chunk_size=3000)


def validate_polished_chunk(
    original: str,
    polished: str,
    _file_path: Path,
    _index: int,
) -> bool:
    return validate_word_count(
        original,
        polished,
        tolerance=POLISH_WORD_TOLERANCE,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    config = RunnerConfig(
        input_dir=Path("output/extracted"),
        output_dir=Path("output/polished"),
        chunker=build_chunks,
        generate=polish_text,
        validator=validate_polished_chunk,
        pacing_seconds=INTER_CALL_PACING_SECONDS,
        label="polishing",
    )
    result = run(
        config,
        file=args.file,
        folder=args.folder,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
