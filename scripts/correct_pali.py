#!/usr/bin/env python3
"""Corrects Pāli phonetic spellings in transcribed text using configured LLM providers."""

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from tools import printer as _p
from tools.chunk_runner import FileRunResult, RunnerConfig, RunResult, run
from tools.pali import (
    apply_overrides,
    chunk_text_no_overlap,
    get_pali_system_instruction,
)
from tools.provider import (
    TEST_MODE,
    build_cacheable_contents,
    generate_with_timeout,
)

pr = _p.printer

INTER_CALL_PACING_SECONDS = 2.0
REPORT_DIR = Path("reports/pali_corrections")


@dataclass(frozen=True)
class CorrectionPair:
    original: str
    corrected: str


@dataclass(frozen=True)
class AppliedCorrection:
    chunk_index: int
    original: str
    corrected: str
    count: int


def generate_pali_corrections(chunk: str, file_path: Path) -> str:
    system_instruction = get_pali_system_instruction(file_path)
    corrected_chunk, _applied = apply_overrides(chunk)
    return generate_with_timeout(
        contents=build_cacheable_contents(corrected_chunk),
        system_instruction=system_instruction,
    )


def correct_pali_transcription(chunk: str, file_path: Path) -> str:
    corrected_chunk, _pre_pass_applied = apply_overrides(chunk)
    response = generate_pali_corrections(chunk, file_path)
    corrected, _applied = apply_correction_response(
        corrected_chunk,
        response,
        chunk_index=0,
    )
    return corrected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Correct Pāli terms in transcripts.")
    parser.add_argument("file", nargs="?", help="Specific file or folder to process")
    parser.add_argument(
        "--folder",
        help="Process all files in this subfolder of output/transcribed",
    )
    parser.add_argument("--limit", type=int, help="Limit to first N unprocessed files")
    return parser


def build_chunks(text: str) -> list[str]:
    chunks = chunk_text_no_overlap(text)
    if TEST_MODE:
        return chunks[:3]
    return chunks


def apply_correction_response(
    chunk: str,
    response: str,
    chunk_index: int,
) -> tuple[str, list[AppliedCorrection]]:
    try:
        pairs = parse_correction_pairs(response)
    except json.JSONDecodeError as exc:
        pr.amber(f"  Warning: JSON correction failed for chunk: {exc}")
        return chunk, []

    corrected_chunk = chunk
    applied: list[AppliedCorrection] = []
    for pair in pairs:
        pattern = re.compile(rf"\b{re.escape(pair.original)}\b", re.IGNORECASE)
        corrected_chunk, count = pattern.subn(pair.corrected, corrected_chunk)
        if count:
            applied.append(
                AppliedCorrection(
                    chunk_index=chunk_index,
                    original=pair.original,
                    corrected=pair.corrected,
                    count=count,
                )
            )

    return corrected_chunk, applied


def parse_correction_pairs(response: str) -> list[CorrectionPair]:
    json_str = response.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:].strip()
    if json_str.endswith("```"):
        json_str = json_str[:-3].strip()

    parsed = json.loads(json_str)
    if not isinstance(parsed, list):
        return []

    pairs: list[CorrectionPair] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if "original" not in item or "corrected" not in item:
            continue
        pairs.append(
            CorrectionPair(
                original=str(item["original"]),
                corrected=str(item["corrected"]),
            )
        )
    return pairs


class CorrectionRecorder:
    def __init__(self) -> None:
        self.applied_by_file: dict[Path, list[AppliedCorrection]] = {}

    def transform(
        self,
        chunk: str,
        response: str,
        file_path: Path,
        chunk_index: int,
    ) -> str:
        corrected_chunk, pre_pass_applied = apply_overrides(chunk)
        self.applied_by_file.setdefault(file_path, []).extend(
            AppliedCorrection(
                chunk_index=chunk_index,
                original=fix.original,
                corrected=fix.corrected,
                count=fix.count,
            )
            for fix in pre_pass_applied
        )
        corrected, applied = apply_correction_response(
            corrected_chunk,
            response,
            chunk_index=chunk_index,
        )
        self.applied_by_file.setdefault(file_path, []).extend(applied)
        return corrected


def write_correction_logs(
    result: RunResult,
    recorder: CorrectionRecorder,
    input_dir: Path,
    report_dir: Path = REPORT_DIR,
) -> None:
    for file_result in result.files:
        if file_result.status != "success":
            continue
        report_path = _correction_report_path(
            file_result,
            input_dir=input_dir,
            report_dir=report_dir,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        applied = recorder.applied_by_file.get(file_result.input_path, [])
        report_path.write_text(
            json.dumps(
                [asdict(item) for item in applied], indent=2, ensure_ascii=False
            ),
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    input_dir = Path("output/transcribed")
    recorder = CorrectionRecorder()
    config = RunnerConfig(
        input_dir=input_dir,
        output_dir=Path("output/corrected_pali"),
        chunker=build_chunks,
        generate=generate_pali_corrections,
        result_transformer=recorder.transform,
        pacing_seconds=INTER_CALL_PACING_SECONDS,
        label="correcting",
    )
    result = run(
        config,
        file=args.file,
        folder=args.folder,
        limit=args.limit,
    )
    write_correction_logs(result, recorder, input_dir=input_dir)
    return result.exit_code


def _correction_report_path(
    file_result: FileRunResult,
    input_dir: Path,
    report_dir: Path,
) -> Path:
    try:
        relative_path = file_result.input_path.relative_to(input_dir)
    except ValueError:
        relative_path = Path(file_result.input_path.name)
    return report_dir / relative_path.with_suffix(".json")


if __name__ == "__main__":
    raise SystemExit(main())
