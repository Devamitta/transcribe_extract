"""Runs golden-set LLM judge evaluations for Pali, extraction, and polish stages."""

from __future__ import annotations

import argparse
import os
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from tools import printer as _p
from tools import antigravity_cli
from tools.eval_judge import (
    DEFAULT_GOLDEN_ROOT,
    DEFAULT_HISTORY_PATH,
    JUDGE_MODEL,
    STAGE_CONFIGS,
    CriterionScore,
    DeterministicCheck,
    JudgeParseResult,
    StageEvalConfig,
    StageName,
    append_history,
    build_judge_prompt,
    criterion_means,
    detect_regression,
    load_history,
    overall_mean,
    parse_judge_response,
    prompt_hash,
    run_deterministic_checks,
)
from tools.incremental import finalize_temp, get_temp_path, load_temp, save_temp

pr = _p.printer

GOLDEN_ROOT = DEFAULT_GOLDEN_ROOT
HISTORY_PATH = DEFAULT_HISTORY_PATH
REPORT_DIR = Path("reports/eval")
INTER_CALL_PACING_SECONDS = 2.0
STAGE_ORDER: tuple[StageName, ...] = ("pali", "extract", "polish")
ALLOWED_PROVIDERS = {"agy", "antigravity-cli"}


@dataclass(frozen=True)
class GoldenExcerpt:
    """One discovered golden-set excerpt and its original source path."""

    stage: StageName
    path: Path
    source_path: Path


@dataclass(frozen=True)
class ExcerptResult:
    """Serializable evaluation result for one golden-set excerpt."""

    stage: StageName
    excerpt_path: str
    source_path: str
    judge: JudgeParseResult
    deterministic_checks: list[DeterministicCheck]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and self.judge.ok
            and all(check.passed for check in self.deterministic_checks)
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate current LLM stage prompts against the golden set."
    )
    parser.add_argument("--stage", choices=STAGE_ORDER, help="Evaluate one stage only")
    parser.add_argument("--limit", type=int, help="Limit excerpts per selected stage")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Evaluate the first 2 excerpts per selected stage",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    provider = os.getenv("PROVIDER", "google").lower()
    if provider not in ALLOWED_PROVIDERS:
        pr.bip()
        pr.no("PROVIDER must be agy or antigravity-cli")
        return 1

    if not probe_judge_model():
        return 1

    stages = selected_stages(args.stage)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"eval_{timestamp}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    all_stage_results: dict[StageName, list[ExcerptResult]] = {}
    hard_failure = False
    regression_detected = False
    generation_models = active_generation_models()
    sampled = is_sampled_run(test=args.test, limit=args.limit)
    mode = run_mode(test=args.test, limit=args.limit)

    for stage in stages:
        config = STAGE_CONFIGS[stage]
        excerpts = discover_golden_excerpts(
            stage=stage,
            limit=args.limit,
            test=args.test,
            golden_root=GOLDEN_ROOT,
        )
        if not excerpts:
            pr.bip()
            pr.no(f"No golden excerpts found for {stage}")
            hard_failure = True
            continue

        stage_results = run_stage(config, excerpts)
        all_stage_results[stage] = stage_results
        stage_failed = any(not result.ok for result in stage_results)
        if stage_failed:
            hard_failure = True
            continue

        means = criterion_means(
            [result.judge for result in stage_results],
            config.criteria,
        )
        entry: dict[str, object] = {
            "timestamp": timestamp,
            "stage": stage,
            "prompt_hash": prompt_hash(stage),
            "generation_models": generation_models,
            "judge_model": JUDGE_MODEL,
            "criterion_means": means,
            "overall_mean": overall_mean(means),
            "excerpt_count": len(stage_results),
            "run_mode": mode,
            "sampled": sampled,
        }
        history_before = load_history(HISTORY_PATH)
        if sampled:
            regression = None
            pr.green(f"Skipping regression gate for sampled {stage} run")
        else:
            regression = detect_regression(
                comparable_full_run_history(
                    history_before,
                    stage=stage,
                    excerpt_count=len(stage_results),
                ),
                entry,
            )
        append_history(entry, HISTORY_PATH)
        if regression is not None and regression.regressed:
            regression_detected = True
            pr.amber(
                f"[REGRESSION] {stage}: {regression.previous_mean:.2f} -> "
                f"{regression.current_mean:.2f} (drop {regression.drop:.2f})"
            )

    write_report(report_path, all_stage_results)
    pr.green(f"Wrote report: {report_path}")

    if hard_failure:
        return 1
    if regression_detected:
        return 2
    return 0


def selected_stages(stage: str | None) -> list[StageName]:
    if stage is None:
        return list(STAGE_ORDER)
    return [cast(StageName, stage)]


def is_sampled_run(*, test: bool, limit: int | None) -> bool:
    return test or limit is not None


def run_mode(*, test: bool, limit: int | None) -> str:
    if test:
        return "test"
    if limit is not None:
        return "limited"
    return "full"


def comparable_full_run_history(
    history: list[dict[str, object]],
    *,
    stage: StageName,
    excerpt_count: int,
) -> list[dict[str, object]]:
    comparable: list[dict[str, object]] = []
    for entry in history:
        if entry.get("stage") != stage:
            continue
        if entry.get("excerpt_count") != excerpt_count:
            continue
        if entry.get("sampled") is True:
            continue
        run_mode_value = entry.get("run_mode")
        if run_mode_value not in (None, "full"):
            continue
        comparable.append(entry)
    return comparable


def probe_judge_model() -> bool:
    pr.green(f"Checking judge model: {JUDGE_MODEL}")
    pr.bip()
    if antigravity_cli.get_working_key(JUDGE_MODEL):
        pr.yes("judge ready")
        return True
    pr.no("judge unavailable")
    return False


def active_generation_models() -> list[str]:
    from tools import provider

    if provider.CLI_TEST_MODE:
        return list(provider.ANTIGRAVITY_CLI_TEST_MODELS)
    return list(provider.ANTIGRAVITY_CLI_WORK_MODELS)


def discover_golden_excerpts(
    *,
    stage: StageName,
    limit: int | None,
    test: bool,
    golden_root: Path,
) -> list[GoldenExcerpt]:
    stage_dir = golden_root / stage
    if not stage_dir.exists():
        return []

    manifest_sources = load_manifest_sources(golden_root)
    paths = sorted(stage_dir.glob("*.md"), key=lambda item: _nfc(str(item)))
    max_items = 2 if test else None
    if limit is not None:
        max_items = limit if max_items is None else min(max_items, limit)
    if max_items is not None:
        paths = paths[:max_items]

    excerpts: list[GoldenExcerpt] = []
    for path in paths:
        source_path = manifest_sources.get(_manifest_key(path), path)
        excerpts.append(GoldenExcerpt(stage=stage, path=path, source_path=source_path))
    return excerpts


def load_manifest_sources(golden_root: Path) -> dict[str, Path]:
    manifest_path = golden_root / "manifest.md"
    if not manifest_path.exists():
        return {}

    sources: dict[str, Path] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        excerpt = parts[1].strip().strip("`")
        source = parts[2].strip().strip("`")
        if excerpt and source:
            sources[_nfc(excerpt)] = Path(source)
    return sources


def run_stage(
    config: StageEvalConfig,
    excerpts: list[GoldenExcerpt],
) -> list[ExcerptResult]:
    temp_path = get_stage_temp_path(config.name)
    saved_results = deserialize_results(load_temp(temp_path), config)
    results = saved_results[: len(excerpts)]

    if results:
        pr.green(
            f"Resuming {config.name} from excerpt {len(results) + 1}/{len(excerpts)}"
        )

    for excerpt in excerpts[len(results) :]:
        result = evaluate_excerpt(config, excerpt)
        results.append(result)
        save_temp(temp_path, [serialize_result(item) for item in results])

    finalize_temp(temp_path)
    return results


def get_stage_temp_path(stage: StageName) -> Path:
    return get_temp_path(REPORT_DIR / f"{stage}.json")


def evaluate_excerpt(config: StageEvalConfig, excerpt: GoldenExcerpt) -> ExcerptResult:
    source_text = excerpt.path.read_text(encoding="utf-8")
    prepared_source = config.prepare_source(source_text)
    try:
        pr.green(f"{config.name}: generating {excerpt.path.name}")
        pr.bip()
        candidate = generate_candidate(config, excerpt.source_path, prepared_source)
        pr.yes("generated")
        time.sleep(INTER_CALL_PACING_SECONDS)

        pr.green(f"{config.name}: judging {excerpt.path.name}")
        pr.bip()
        judge_response = judge_candidate(config, source_text, candidate)
        pr.yes("judged")
        time.sleep(INTER_CALL_PACING_SECONDS)
    except Exception as error:
        error_message = str(error) or error.__class__.__name__
        return ExcerptResult(
            stage=config.name,
            excerpt_path=str(excerpt.path),
            source_path=str(excerpt.source_path),
            judge=JudgeParseResult(ok=False, scores={}, error=error_message),
            deterministic_checks=[],
            error=error_message,
        )

    judge = parse_judge_response(judge_response, config.criteria)
    checks = run_deterministic_checks(config, source_text, candidate)
    return ExcerptResult(
        stage=config.name,
        excerpt_path=str(excerpt.path),
        source_path=str(excerpt.source_path),
        judge=judge,
        deterministic_checks=checks,
    )


def generate_candidate(
    config: StageEvalConfig,
    source_path: Path,
    prepared_source: str,
) -> str:
    from tools.provider import build_cacheable_contents, generate_with_timeout

    return generate_with_timeout(
        contents=build_cacheable_contents(prepared_source),
        system_instruction=config.build_system_instruction(source_path),
    )


def judge_candidate(
    config: StageEvalConfig,
    source_text: str,
    candidate_output: str,
) -> str:
    return antigravity_cli.generate_content(
        contents=build_judge_prompt(config, source_text, candidate_output),
        system_instruction="Return strict JSON only.",
        model=JUDGE_MODEL,
        max_output_tokens=8192,
        temperature=0.0,
    )


def write_report(
    report_path: Path,
    stage_results: dict[StageName, list[ExcerptResult]],
) -> None:
    lines = [f"# Stage Evaluation: {report_path.stem}", ""]
    for stage in STAGE_ORDER:
        results = stage_results.get(stage)
        if not results:
            continue
        config = STAGE_CONFIGS[stage]
        means = criterion_means([result.judge for result in results], config.criteria)
        lines.append(f"## {stage}")
        lines.append("")
        lines.append(f"- Overall mean: {overall_mean(means):.2f}")
        for criterion in config.criteria:
            lines.append(f"- {criterion.label}: {means[criterion.key]:.2f}")
        lines.append("")

        for result in results:
            lines.append(f"### {Path(result.excerpt_path).name}")
            lines.append("")
            lines.append(f"- Source: `{result.source_path}`")
            lines.append(f"- Status: {'pass' if result.ok else 'fail'}")
            if result.error is not None:
                lines.append(f"- Error: {result.error}")
            if result.judge.error is not None:
                lines.append(f"- Judge parse: {result.judge.error}")
            for check in result.deterministic_checks:
                status = "pass" if check.passed else "fail"
                lines.append(
                    f"- Deterministic `{check.name}`: {status} - {check.details}"
                )
            if result.judge.scores:
                lines.append("")
                lines.append("| Criterion | Score | Reason |")
                lines.append("| --- | ---: | --- |")
                for criterion in config.criteria:
                    score = result.judge.scores[criterion.key]
                    lines.append(
                        f"| {criterion.label} | {score.score} | "
                        f"{_escape_table(score.reason)} |"
                    )
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def serialize_result(result: ExcerptResult) -> dict[str, object]:
    return {
        "stage": result.stage,
        "excerpt_path": result.excerpt_path,
        "source_path": result.source_path,
        "judge": serialize_judge(result.judge),
        "deterministic_checks": [
            {
                "name": check.name,
                "passed": check.passed,
                "details": check.details,
            }
            for check in result.deterministic_checks
        ],
        "error": result.error,
    }


def serialize_judge(judge: JudgeParseResult) -> dict[str, object]:
    return {
        "ok": judge.ok,
        "error": judge.error,
        "scores": {
            key: {"score": score.score, "reason": score.reason}
            for key, score in judge.scores.items()
        },
    }


def deserialize_results(raw: object, config: StageEvalConfig) -> list[ExcerptResult]:
    if not isinstance(raw, list):
        return []
    results: list[ExcerptResult] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            results.append(deserialize_result(cast(dict[str, object], item), config))
        except (KeyError, TypeError, ValueError):
            continue
    return results


def deserialize_result(
    raw: dict[str, object],
    config: StageEvalConfig,
) -> ExcerptResult:
    judge = deserialize_judge(raw["judge"])
    checks = deserialize_checks(raw.get("deterministic_checks", []))
    error_value = raw.get("error")
    return ExcerptResult(
        stage=config.name,
        excerpt_path=str(raw["excerpt_path"]),
        source_path=str(raw["source_path"]),
        judge=judge,
        deterministic_checks=checks,
        error=error_value if isinstance(error_value, str) else None,
    )


def deserialize_judge(raw: object) -> JudgeParseResult:
    if not isinstance(raw, dict):
        raise TypeError("judge must be an object")
    raw_scores = raw.get("scores", {})
    if not isinstance(raw_scores, dict):
        raise TypeError("judge scores must be an object")

    scores: dict[str, CriterionScore] = {}
    for key, value in raw_scores.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        score = value.get("score")
        reason = value.get("reason")
        if isinstance(score, int) and isinstance(reason, str):
            scores[key] = CriterionScore(score=score, reason=reason)

    return JudgeParseResult(
        ok=bool(raw.get("ok")),
        scores=scores,
        error=raw["error"] if isinstance(raw.get("error"), str) else None,
    )


def deserialize_checks(raw: object) -> list[DeterministicCheck]:
    if not isinstance(raw, list):
        return []
    checks: list[DeterministicCheck] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        passed = item.get("passed")
        details = item.get("details")
        if (
            isinstance(name, str)
            and isinstance(passed, bool)
            and isinstance(details, str)
        ):
            checks.append(DeterministicCheck(name=name, passed=passed, details=details))
    return checks


def _manifest_key(path: Path) -> str:
    try:
        return _nfc(str(path.relative_to(Path.cwd())))
    except ValueError:
        return _nfc(str(path))


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
