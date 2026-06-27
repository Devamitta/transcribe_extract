"""Provides stage-evaluation helpers for golden-set LLM judge runs."""

from __future__ import annotations

import difflib
import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias, cast

from tools.extract import EXTRACT_SYSTEM_INSTRUCTION
from tools.pali import DATA_DIR, apply_overrides, get_pali_system_instruction
from tools.polish import POLISH_SYSTEM_INSTRUCTION, POLISH_WORD_TOLERANCE

StageName: TypeAlias = Literal["pali", "extract", "polish"]
PromptBuilder: TypeAlias = Callable[[Path], str]
SourcePreparer: TypeAlias = Callable[[str], str]
DeterministicCheckFn: TypeAlias = Callable[[str, str], "DeterministicCheck"]

DEFAULT_GOLDEN_ROOT = Path("eval/golden")
DEFAULT_HISTORY_PATH = Path("reports/eval/history.json")
PALI_HASH_DATA_FILES = (
    DATA_DIR / "pali_overrides.json",
    DATA_DIR / "pali_examples.json",
)
REGRESSION_THRESHOLD = 0.5


@dataclass(frozen=True)
class Criterion:
    """Judge rubric criterion."""

    key: str
    label: str
    description: str


@dataclass(frozen=True)
class CriterionScore:
    """Parsed judge score for one criterion."""

    score: int
    reason: str


@dataclass(frozen=True)
class JudgeParseResult:
    """Parsed judge response or a recoverable parse failure."""

    ok: bool
    scores: dict[str, CriterionScore]
    error: str | None = None


@dataclass(frozen=True)
class DeterministicCheck:
    """Non-LLM validation result for a candidate stage output."""

    name: str
    passed: bool
    details: str


@dataclass(frozen=True)
class RegressionResult:
    """Regression comparison against the previous stage history entry."""

    regressed: bool
    previous_mean: float | None
    current_mean: float
    drop: float


@dataclass(frozen=True)
class StageEvalConfig:
    """Configuration for evaluating one pipeline LLM stage."""

    name: StageName
    golden_dir: Path
    prompt_hash_path: Path
    build_system_instruction: PromptBuilder
    prepare_source: SourcePreparer
    criteria: tuple[Criterion, ...]
    deterministic_checks: tuple[DeterministicCheckFn, ...] = ()


def _identity(text: str) -> str:
    return text


def _prepare_pali_source(text: str) -> str:
    corrected, _applied = apply_overrides(text)
    return corrected


def _constant_prompt(instruction: str) -> PromptBuilder:
    def _build(_file_path: Path) -> str:
        return instruction

    return _build


PALI_CRITERIA = (
    Criterion(
        key="pali_restoration",
        label="Pali restoration correctness",
        description="Corrections restore intended Pali/Buddhist terms accurately.",
    ),
    Criterion(
        key="no_meaning_flip",
        label="No meaning-flips or over-correction",
        description="The output does not change the teaching meaning or over-correct valid text.",
    ),
    Criterion(
        key="non_pali_preserved",
        label="Non-Pali text preserved verbatim",
        description="Non-Pali speech remains unchanged except for intended local corrections.",
    ),
)

EXTRACT_CRITERIA = (
    Criterion(
        key="completeness",
        label="Completeness",
        description="No meaningful teaching content from the source is lost.",
    ),
    Criterion(
        key="fidelity",
        label="Fidelity",
        description="The output does not invent teachings, facts, or explanations.",
    ),
    Criterion(
        key="deidentification",
        label="De-identification",
        description="Names, places, monasteries, and private identifiers are removed or generalized.",
    ),
    Criterion(
        key="structure",
        label="Structure",
        description="Uses `## [tag]` sections to organize topics; no invented speaker attribution.",
    ),
)

POLISH_CRITERIA = (
    Criterion(
        key="content_fidelity",
        label="Content fidelity",
        description="No teaching detail, exchange, or nuance is lost or added.",
    ),
    Criterion(
        key="readability",
        label="Readability improvement",
        description="Grammar and flow improve while preserving the speaker's meaning.",
    ),
    Criterion(
        key="structure_preservation",
        label="Structure preservation",
        description="Headers and topic tags are preserved.",
    ),
)


def check_extract_word_ratio(source: str, candidate: str) -> DeterministicCheck:
    """Check that extraction output is at least half the source word count."""

    source_words = len(source.split())
    candidate_words = len(candidate.split())
    if source_words == 0:
        passed = candidate_words == 0
        ratio = 1.0 if passed else 0.0
    else:
        ratio = candidate_words / source_words
        passed = ratio >= 0.5
    return DeterministicCheck(
        name="extract_min_word_ratio",
        passed=passed,
        details=(
            f"candidate/source word ratio {ratio:.1%} "
            f"({candidate_words}/{source_words}, minimum 50.0%)"
        ),
    )


def check_polish_word_tolerance(source: str, candidate: str) -> DeterministicCheck:
    """Check that polish output stays within the configured word-count tolerance."""

    source_words = len(source.split())
    candidate_words = len(candidate.split())
    if source_words == 0:
        passed = candidate_words == 0
        difference = 0.0 if passed else 1.0
    else:
        difference = abs(source_words - candidate_words) / source_words
        passed = difference <= POLISH_WORD_TOLERANCE
    return DeterministicCheck(
        name="polish_word_tolerance",
        passed=passed,
        details=(
            f"word-count drift {difference:.1%} "
            f"({candidate_words}/{source_words}, tolerance {POLISH_WORD_TOLERANCE:.1%})"
        ),
    )


STAGE_CONFIGS: dict[StageName, StageEvalConfig] = {
    "pali": StageEvalConfig(
        name="pali",
        golden_dir=DEFAULT_GOLDEN_ROOT / "pali",
        prompt_hash_path=Path("output/transcribed/interview/eval.md"),
        build_system_instruction=get_pali_system_instruction,
        prepare_source=_prepare_pali_source,
        criteria=PALI_CRITERIA,
    ),
    "extract": StageEvalConfig(
        name="extract",
        golden_dir=DEFAULT_GOLDEN_ROOT / "extract",
        prompt_hash_path=Path("output/corrected_pali/interview/eval.md"),
        build_system_instruction=_constant_prompt(EXTRACT_SYSTEM_INSTRUCTION),
        prepare_source=_identity,
        criteria=EXTRACT_CRITERIA,
        deterministic_checks=(check_extract_word_ratio,),
    ),
    "polish": StageEvalConfig(
        name="polish",
        golden_dir=DEFAULT_GOLDEN_ROOT / "polish",
        prompt_hash_path=Path("output/extracted/interview/eval.md"),
        build_system_instruction=_constant_prompt(POLISH_SYSTEM_INSTRUCTION),
        prepare_source=_identity,
        criteria=POLISH_CRITERIA,
        deterministic_checks=(check_polish_word_tolerance,),
    ),
}


def get_stage_config(stage: str) -> StageEvalConfig:
    """Return a stage config, raising a clear error for unknown stages."""

    if stage not in STAGE_CONFIGS:
        valid = ", ".join(sorted(STAGE_CONFIGS))
        raise ValueError(f"Unknown stage {stage!r}; expected one of: {valid}")
    return STAGE_CONFIGS[cast(StageName, stage)]


def build_judge_prompt(
    config: StageEvalConfig,
    source_text: str,
    candidate_output: str,
) -> str:
    """Build the strict-JSON judge prompt for one excerpt.

    CANDIDATE OUTPUT is placed before SOURCE EXCERPT (not after) because the
    antigravity-cli path silently drops prompt content past roughly 65-78k
    characters — confirmed by direct reproduction (full-length prompts with a
    large source lost the candidate entirely; the same content reordered so
    candidate comes first was read correctly). The candidate is normally far
    smaller than the source, so putting it first keeps it inside the safe
    window even when the source alone would overflow it.
    """

    criteria_lines = "\n".join(
        f"- {criterion.key}: {criterion.label}. {criterion.description}"
        for criterion in config.criteria
    )
    keys = ", ".join(criterion.key for criterion in config.criteria)
    return (
        "You are judging one candidate output from a Dhamma transcript pipeline.\n"
        "Score each criterion from 1 to 5 where 1 is unusable and 5 is excellent.\n"
        "Use only the source excerpt and candidate output. Do not reward invented content.\n"
        "Return strict JSON only. Do not wrap it in Markdown.\n\n"
        f"STAGE: {config.name}\n\n"
        "CRITERIA:\n"
        f"{criteria_lines}\n\n"
        "JSON SHAPE:\n"
        "{\n"
        f'  "{keys.split(", ")[0]}": {{"score": 1, "reason": "one-line reason"}}\n'
        "}\n"
        "Include every criterion key exactly once. Valid keys: "
        f"{keys}.\n\n"
        "CANDIDATE OUTPUT:\n"
        f"{candidate_output}\n\n"
        "SOURCE EXCERPT:\n"
        f"{source_text}\n"
    )


def strip_json_fence(response: str) -> str:
    """Strip common Markdown JSON fences from a model response."""

    json_str = response.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:].strip()
    elif json_str.startswith("```"):
        json_str = json_str[3:].strip()
    if json_str.endswith("```"):
        json_str = json_str[:-3].strip()
    return json_str


FUZZY_KEY_MATCH_CUTOFF = 0.8


def _resolve_criterion_key(
    criterion_key: str,
    parsed: dict[str, object],
    claimed_keys: set[str],
) -> str | None:
    """Find the JSON key for a criterion, tolerating judge-model misspellings.

    The judge model is observed to occasionally typo a criterion key (e.g.
    "readibility" for "readability") while keeping the rest of the JSON shape
    intact. Exact match first; otherwise fall back to the closest unclaimed
    key by string similarity, so a single-letter typo doesn't fail the whole
    parse.
    """

    if criterion_key in parsed and criterion_key not in claimed_keys:
        return criterion_key

    candidates = [
        key for key in parsed if key not in claimed_keys and key != criterion_key
    ]
    matches = difflib.get_close_matches(
        criterion_key, candidates, n=1, cutoff=FUZZY_KEY_MATCH_CUTOFF
    )
    return matches[0] if matches else None


def parse_judge_response(
    response: str,
    criteria: Sequence[Criterion],
) -> JudgeParseResult:
    """Parse a judge JSON response and return a recoverable failure on malformed input."""

    try:
        parsed = json.loads(strip_json_fence(response))
    except json.JSONDecodeError as error:
        return JudgeParseResult(ok=False, scores={}, error=f"Invalid JSON: {error}")

    if not isinstance(parsed, dict):
        return JudgeParseResult(
            ok=False, scores={}, error="Judge JSON was not an object"
        )

    scores: dict[str, CriterionScore] = {}
    claimed_keys: set[str] = set()
    for criterion in criteria:
        resolved_key = _resolve_criterion_key(criterion.key, parsed, claimed_keys)
        if resolved_key is None:
            return JudgeParseResult(
                ok=False,
                scores={},
                error=f"Missing criterion object: {criterion.key}",
            )
        claimed_keys.add(resolved_key)
        raw_score = parsed.get(resolved_key)
        if not isinstance(raw_score, dict):
            return JudgeParseResult(
                ok=False,
                scores={},
                error=f"Missing criterion object: {criterion.key}",
            )
        score_value = raw_score.get("score")
        reason = raw_score.get("reason")
        if not isinstance(score_value, int) or not 1 <= score_value <= 5:
            return JudgeParseResult(
                ok=False,
                scores={},
                error=f"Invalid score for criterion: {criterion.key}",
            )
        if not isinstance(reason, str) or not reason.strip():
            return JudgeParseResult(
                ok=False,
                scores={},
                error=f"Invalid reason for criterion: {criterion.key}",
            )
        scores[criterion.key] = CriterionScore(score=score_value, reason=reason.strip())

    return JudgeParseResult(ok=True, scores=scores)


def run_deterministic_checks(
    config: StageEvalConfig,
    source_text: str,
    candidate_output: str,
) -> list[DeterministicCheck]:
    """Run non-LLM checks configured for a stage."""

    return [
        check(source_text, candidate_output) for check in config.deterministic_checks
    ]


def prompt_hash(
    stage: str,
    *,
    file_path: Path | None = None,
    data_paths: Sequence[Path] | None = None,
) -> str:
    """Hash the assembled stage instruction and relevant data-file bytes."""

    config = get_stage_config(stage)
    hasher = hashlib.sha256()
    instruction_path = file_path if file_path is not None else config.prompt_hash_path
    hasher.update(config.build_system_instruction(instruction_path).encode("utf-8"))

    if config.name == "pali":
        hash_data_paths = data_paths if data_paths is not None else PALI_HASH_DATA_FILES
        for path in hash_data_paths:
            hasher.update(path.read_bytes())

    return hasher.hexdigest()


def load_history(history_path: Path = DEFAULT_HISTORY_PATH) -> list[dict[str, object]]:
    """Load the append-only eval history, returning an empty list if missing."""

    if not history_path.exists():
        return []
    raw = json.loads(history_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Expected history list in {history_path}")
    return [item for item in raw if isinstance(item, dict)]


def append_history(
    entry: dict[str, object],
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> list[dict[str, object]]:
    """Append one history entry and persist the full history list."""

    history = load_history(history_path)
    history.append(entry)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return history


def detect_regression(
    history: Sequence[dict[str, object]],
    new_entry: dict[str, object],
    *,
    threshold: float = REGRESSION_THRESHOLD,
) -> RegressionResult:
    """Compare a new stage score with the previous history entry for that stage."""

    stage = new_entry.get("stage")
    if not isinstance(stage, str):
        raise ValueError("History entry is missing string field: stage")
    current_mean = _as_float(new_entry.get("overall_mean"), "overall_mean")

    previous_mean: float | None = None
    for entry in reversed(history):
        if entry is new_entry:
            continue
        if entry.get("stage") != stage:
            continue
        previous_mean = _as_float(entry.get("overall_mean"), "overall_mean")
        break

    if previous_mean is None:
        return RegressionResult(
            regressed=False,
            previous_mean=None,
            current_mean=current_mean,
            drop=0.0,
        )

    drop = previous_mean - current_mean
    return RegressionResult(
        regressed=drop >= threshold,
        previous_mean=previous_mean,
        current_mean=current_mean,
        drop=drop,
    )


def criterion_means(
    judge_results: Sequence[JudgeParseResult],
    criteria: Sequence[Criterion],
) -> dict[str, float]:
    """Calculate per-criterion means across successful judge results."""

    successful = [result for result in judge_results if result.ok]
    if not successful:
        return {criterion.key: 0.0 for criterion in criteria}
    return {
        criterion.key: sum(result.scores[criterion.key].score for result in successful)
        / len(successful)
        for criterion in criteria
    }


def overall_mean(means: dict[str, float]) -> float:
    """Calculate the overall mean from criterion means."""

    if not means:
        return 0.0
    return sum(means.values()) / len(means)


def _as_float(value: object, field_name: str) -> float:
    if isinstance(value, int | float):
        return float(value)
    raise ValueError(f"History entry is missing numeric field: {field_name}")
