#!/usr/bin/env python3
"""Extracts core Dhamma teachings from corrected transcripts into structured Q&A format with Pāli topic tags."""

import argparse
from pathlib import Path

from tools import printer as _p
from tools.chunk_runner import (
    FileRunResult,
    RunnerConfig,
    RunResult,
    run,
)
from tools.chunking import chunk_text_by_paragraph
from tools.extract import EXTRACT_SYSTEM_INSTRUCTION as SYSTEM_INSTRUCTION
from tools.extract import is_no_points
from tools.polish import validate_word_count
from tools.provider import (
    build_cacheable_contents,
    generate_with_timeout,
)

pr = _p.printer

INTER_CALL_PACING_SECONDS = 5.0


def extract_dhamma_points(text: str, _file_path: Path | None = None) -> str:
    return generate_with_timeout(
        contents=build_cacheable_contents(text),
        system_instruction=SYSTEM_INSTRUCTION,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract Dhamma teachings from corrected transcripts."
    )
    parser.add_argument("file", nargs="?", help="Specific file to process")
    parser.add_argument(
        "--folder", help="Process all files in this subfolder (e.g. interview)"
    )
    parser.add_argument("--limit", type=int, help="Limit to first N unprocessed files")
    return parser


def build_chunks(text: str) -> list[str]:
    return chunk_text_by_paragraph(text, chunk_size=4000)


def transform_extract_result(
    _chunk: str,
    result: str,
    _file_path: Path,
    _index: int,
) -> str:
    if is_no_points(result):
        return ""
    return result.strip()


def report_low_ratio_warnings(result: RunResult) -> int:
    warnings = 0
    for file_result in result.files:
        if file_result.status != "success":
            continue
        if _is_low_output_ratio(file_result):
            warnings += 1
            pr.amber(
                f"[WARN] {file_result.output_path} output below 50% of input word count"
            )
    pr.summary("low ratio warnings", warnings)
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    config = RunnerConfig(
        input_dir=Path("output/corrected_pali"),
        output_dir=Path("output/extracted"),
        chunker=build_chunks,
        generate=extract_dhamma_points,
        result_transformer=transform_extract_result,
        pacing_seconds=INTER_CALL_PACING_SECONDS,
        label="extracting",
    )
    result = run(
        config,
        file=args.file,
        folder=args.folder,
        limit=args.limit,
    )
    report_low_ratio_warnings(result)
    return result.exit_code


def _is_low_output_ratio(file_result: FileRunResult) -> bool:
    original = file_result.input_path.read_text(encoding="utf-8")
    extracted = file_result.output_path.read_text(encoding="utf-8")
    return not validate_word_count(original, extracted, min_ratio=0.5)


if __name__ == "__main__":
    raise SystemExit(main())
