"""Runs production LLM judge evaluations on actual pipeline files to gate quality."""

import argparse
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from tools import printer as _p
from tools.eval_judge import (
    CriterionScore,
    DeterministicCheck,
    JudgeParseResult,
    StageEvalConfig,
    StageName,
    build_judge_prompt,
    get_stage_config,
    parse_judge_response,
    run_deterministic_checks,
)
from tools.incremental import finalize_temp, get_temp_path, load_temp, save_temp
from tools.provider import generate_with_timeout, get_working_key

pr = _p.printer

INTER_CALL_PACING_SECONDS = 2.0
REPORT_DIR = Path("reports/batch")
SIZE_RATIO_TARGET = 0.75
SIZE_RATIO_FLOOR = 0.60
MIN_CRITERION_SCORE = 4


@dataclass(frozen=True)
class Pair:
    source_path: Path
    candidate_path: Path


@dataclass(frozen=True)
class EvalResult:
    source_path: Path
    candidate_path: Path
    judge: JudgeParseResult
    deterministic_checks: list[DeterministicCheck]
    size_ratio: float
    error: str | None = None


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def size_ratio(source_text: str, candidate_text: str) -> float:
    s = len(source_text.split())
    return 1.0 if s == 0 else len(candidate_text.split()) / s


def is_flagged(scores: dict[str, CriterionScore], ratio: float) -> bool:
    return (
        any(cs.score < MIN_CRITERION_SCORE for cs in scores.values())
        or ratio < SIZE_RATIO_FLOOR
    )


def discover_pairs(stage: StageName, folder: str, limit: int | None) -> list[Pair]:
    if stage == "extract":
        source_dir = Path("output/corrected_pali") / folder
        candidate_dir = Path("output/extracted") / folder
    elif stage == "polish":
        source_dir = Path("output/extracted") / folder
        candidate_dir = Path("output/polished") / folder
    else:
        raise ValueError(f"Unknown stage {stage}")

    if not source_dir.exists() or not candidate_dir.exists():
        return []

    sources = sorted(source_dir.glob("*.md"), key=lambda p: _nfc(p.name))
    candidates_index = {_nfc(p.name): p for p in candidate_dir.glob("*.md")}

    pairs: list[Pair] = []
    for source in sources:
        cand = candidates_index.get(_nfc(source.name))
        if cand is not None:
            pairs.append(Pair(source_path=source, candidate_path=cand))

    if limit is not None:
        pairs = pairs[:limit]
    return pairs


def get_stage_temp_path(stage: StageName, folder: str) -> Path:
    return get_temp_path(REPORT_DIR / f"{stage}_{folder}.json")


def evaluate_pair(config: StageEvalConfig, pair: Pair) -> EvalResult:
    source_text = pair.source_path.read_text(encoding="utf-8")
    candidate_text = pair.candidate_path.read_text(encoding="utf-8")
    ratio = size_ratio(source_text, candidate_text)

    try:
        pr.green(f"{config.name}: judging {pair.candidate_path.name}")
        pr.bip()
        judge_response = generate_with_timeout(
            contents=build_judge_prompt(config, source_text, candidate_text),
            system_instruction="Return strict JSON only.",
            max_output_tokens=8192,
            temperature=0.0,
        )
        pr.yes("judged")
        time.sleep(INTER_CALL_PACING_SECONDS)
    except Exception as error:
        error_message = str(error) or error.__class__.__name__
        return EvalResult(
            source_path=pair.source_path,
            candidate_path=pair.candidate_path,
            judge=JudgeParseResult(ok=False, scores={}, error=error_message),
            deterministic_checks=[],
            size_ratio=ratio,
            error=error_message,
        )

    judge = parse_judge_response(judge_response, config.criteria)
    checks = run_deterministic_checks(config, source_text, candidate_text)
    return EvalResult(
        source_path=pair.source_path,
        candidate_path=pair.candidate_path,
        judge=judge,
        deterministic_checks=checks,
        size_ratio=ratio,
    )


def serialize_result(result: EvalResult) -> dict[str, object]:
    return {
        "source_path": str(result.source_path),
        "candidate_path": str(result.candidate_path),
        "judge": {
            "ok": result.judge.ok,
            "error": result.judge.error,
            "scores": {
                k: {"score": v.score, "reason": v.reason}
                for k, v in result.judge.scores.items()
            },
        },
        "deterministic_checks": [
            {
                "name": c.name,
                "passed": c.passed,
                "details": c.details,
            }
            for c in result.deterministic_checks
        ],
        "size_ratio": result.size_ratio,
        "error": result.error,
    }


def deserialize_results(raw: object) -> list[EvalResult]:
    if not isinstance(raw, list):
        return []
    results: list[EvalResult] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            scores: dict[str, CriterionScore] = {}
            judge_data = cast(dict[str, object], item.get("judge", {}))
            raw_scores = cast(
                dict[str, dict[str, object]], judge_data.get("scores", {})
            )
            for k, v in raw_scores.items():
                scores[k] = CriterionScore(
                    score=cast(int, v.get("score", 0)),
                    reason=cast(str, v.get("reason", "")),
                )
            judge = JudgeParseResult(
                ok=cast(bool, judge_data.get("ok", False)),
                scores=scores,
                error=cast(str | None, judge_data.get("error")),
            )

            checks: list[DeterministicCheck] = []
            for check in cast(
                list[dict[str, object]], item.get("deterministic_checks", [])
            ):
                checks.append(
                    DeterministicCheck(
                        name=cast(str, check.get("name", "")),
                        passed=cast(bool, check.get("passed", False)),
                        details=cast(str, check.get("details", "")),
                    )
                )

            results.append(
                EvalResult(
                    source_path=Path(cast(str, item["source_path"])),
                    candidate_path=Path(cast(str, item["candidate_path"])),
                    judge=judge,
                    deterministic_checks=checks,
                    size_ratio=cast(float, item.get("size_ratio", 0.0)),
                    error=cast(str | None, item.get("error")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return results


def write_report(
    report_path: Path,
    results: list[EvalResult],
    stage: StageName,
    folder: str,
    timestamp: str,
) -> None:
    flagged: list[EvalResult] = []
    for result in results:
        if (
            not result.judge.ok
            or is_flagged(result.judge.scores, result.size_ratio)
            or result.error
        ):
            flagged.append(result)

    lines = [
        f"# Batch QC: {stage} / {folder} — {timestamp}",
        "",
        f"- Pairs evaluated: {len(results)}",
        f"- Flagged: {len(flagged)}   |   Clean: {len(results) - len(flagged)}",
        f"- Size target: {int(SIZE_RATIO_TARGET * 100)}%  |  flag floor: {int(SIZE_RATIO_FLOOR * 100)}%",
        "",
    ]

    if flagged:
        lines.append("## Flagged")
        lines.append("")

    for result in flagged:
        lines.append(f"### {result.candidate_path.name}")
        lines.append(f"- Size ratio: {int(result.size_ratio * 100)}%")
        if result.error:
            lines.append(f"- Error: {result.error}")
        if result.judge.error:
            lines.append(f"- Judge error: {result.judge.error}")
        for k, cs in result.judge.scores.items():
            if cs.score < MIN_CRITERION_SCORE:
                lines.append(f"- {k}: {cs.score}/5 — {cs.reason}")
        for check in result.deterministic_checks:
            lines.append(
                f"- Deterministic `{check.name}`: {'pass' if check.passed else 'fail'} — {check.details}"
            )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_stage(
    config: StageEvalConfig, pairs: list[Pair], folder: str
) -> list[EvalResult]:
    temp_path = get_stage_temp_path(config.name, folder)
    saved_results = deserialize_results(load_temp(temp_path))
    results = saved_results[: len(pairs)]

    if results:
        pr.green(f"Resuming {config.name} from pair {len(results) + 1}/{len(pairs)}")

    for pair in pairs[len(results) :]:
        result = evaluate_pair(config, pair)
        results.append(result)
        save_temp(temp_path, [serialize_result(r) for r in results])

    finalize_temp(temp_path)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate actual pipeline output files."
    )
    parser.add_argument(
        "--stage",
        choices=["extract", "polish"],
        required=True,
        help="Stage to evaluate",
    )
    parser.add_argument("--folder", default="interview", help="Input folder name")
    parser.add_argument("--limit", type=int, help="Limit number of pairs")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    pr.green("Checking provider availability")
    pr.bip()
    if get_working_key():
        pr.yes("provider ready")
    else:
        pr.no("no provider available")
        return 1

    stage: StageName = args.stage
    folder: str = args.folder
    config = get_stage_config(stage)

    pairs = discover_pairs(stage, folder, args.limit)
    if not pairs:
        pr.no(f"No pairs found for {stage}/{folder}")
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"batch_{stage}_{folder}_{timestamp}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    results = run_stage(config, pairs, folder)
    write_report(report_path, results, stage, folder, timestamp)
    pr.green(f"Wrote report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
