"""Tests golden-set stage judge helpers without live LLM calls."""

import json
from pathlib import Path

import pytest

from tools.eval_judge import (
    EXTRACT_CRITERIA,
    POLISH_CRITERIA,
    append_history,
    check_extract_word_ratio,
    check_polish_word_tolerance,
    detect_regression,
    load_history,
    parse_judge_response,
    prompt_hash,
)


def _judge_payload() -> dict[str, dict[str, object]]:
    return {
        criterion.key: {"score": 4, "reason": f"{criterion.key} is concrete"}
        for criterion in EXTRACT_CRITERIA
    }


def test_parse_judge_response_accepts_clean_json() -> None:
    result = parse_judge_response(json.dumps(_judge_payload()), EXTRACT_CRITERIA)

    assert result.ok
    assert result.error is None
    assert result.scores["completeness"].score == 4
    assert result.scores["fidelity"].reason == "fidelity is concrete"


def test_parse_judge_response_accepts_fenced_json() -> None:
    response = f"```json\n{json.dumps(_judge_payload())}\n```"

    result = parse_judge_response(response, EXTRACT_CRITERIA)

    assert result.ok
    assert result.scores["structure"].score == 4


def test_parse_judge_response_returns_recoverable_failure_on_malformed_json() -> None:
    result = parse_judge_response("not json", EXTRACT_CRITERIA)

    assert not result.ok
    assert result.scores == {}
    assert result.error is not None
    assert "Invalid JSON" in result.error


def test_regression_detection_flags_drop_at_threshold() -> None:
    history = [
        {"stage": "extract", "overall_mean": 4.2},
        {"stage": "pali", "overall_mean": 3.0},
    ]
    new_entry = {"stage": "extract", "overall_mean": 3.7}

    result = detect_regression(history, new_entry)

    assert result.regressed
    assert result.previous_mean == 4.2
    assert result.current_mean == 3.7
    assert result.drop == pytest.approx(0.5)


def test_regression_detection_ignores_smaller_drop() -> None:
    history = [{"stage": "extract", "overall_mean": 4.2}]
    new_entry = {"stage": "extract", "overall_mean": 3.71}

    result = detect_regression(history, new_entry)

    assert not result.regressed
    assert result.drop == pytest.approx(0.49)


def test_regression_detection_first_entry_never_flags() -> None:
    result = detect_regression([], {"stage": "extract", "overall_mean": 3.7})

    assert not result.regressed
    assert result.previous_mean is None
    assert result.drop == 0.0


def test_append_history_writes_flat_list(tmp_path: Path) -> None:
    history_path = tmp_path / "reports" / "eval" / "history.json"
    first = {"stage": "extract", "overall_mean": 4.0}
    second = {"stage": "polish", "overall_mean": 3.5}

    append_history(first, history_path)
    history = append_history(second, history_path)

    assert history == [first, second]
    assert load_history(history_path) == [first, second]


def test_prompt_hash_changes_when_pali_data_json_changes(tmp_path: Path) -> None:
    overrides = tmp_path / "pali_overrides.json"
    examples = tmp_path / "pali_examples.json"
    overrides.write_text("[]", encoding="utf-8")
    examples.write_text("{}", encoding="utf-8")
    first_hash = prompt_hash(
        "pali",
        file_path=Path("output/transcribed/interview/talk.md"),
        data_paths=(overrides, examples),
    )

    overrides.write_text(
        '[{"original": "winner", "corrected": "Vinaya"}]', encoding="utf-8"
    )
    second_hash = prompt_hash(
        "pali",
        file_path=Path("output/transcribed/interview/talk.md"),
        data_paths=(overrides, examples),
    )

    assert first_hash != second_hash


def test_extract_word_ratio_check_passes_and_fails() -> None:
    source = " ".join(["word"] * 100)

    assert check_extract_word_ratio(source, " ".join(["word"] * 50)).passed
    assert not check_extract_word_ratio(source, " ".join(["word"] * 49)).passed


def test_polish_word_tolerance_check_passes_and_fails() -> None:
    source = " ".join(["word"] * 100)

    assert check_polish_word_tolerance(source, " ".join(["word"] * 115)).passed
    assert not check_polish_word_tolerance(source, " ".join(["word"] * 116)).passed


def test_polish_criteria_match_expected_registry_shape() -> None:
    assert [criterion.key for criterion in POLISH_CRITERIA] == [
        "content_fidelity",
        "readability",
        "structure_preservation",
    ]
