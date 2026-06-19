"""Regression tests for semantic evaluation failure handling."""

from pathlib import Path

import pytest

from scripts import evaluate_semantic


def _write_corrected_transcript(tmp_path: Path) -> Path:
    input_file = tmp_path / "output" / "corrected_pali" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("Corrected transcript body.", encoding="utf-8")
    return input_file


def test_llm_failure_exits_nonzero_without_clean_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_corrected_transcript(tmp_path)

    def fail_generate_with_timeout(**kwargs: str) -> str:
        raise RuntimeError("provider failed")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        evaluate_semantic, "generate_with_timeout", fail_generate_with_timeout
    )
    monkeypatch.setattr(evaluate_semantic, "INTER_CHUNK_SLEEP_SECONDS", 0.0)
    monkeypatch.setattr(evaluate_semantic, "INTER_FILE_SLEEP_SECONDS", 0.0)

    result = evaluate_semantic.main([])

    report = tmp_path / "reports" / "semantic" / "talk.md"
    assert result == 1
    assert not report.exists()


def test_parse_failure_exits_nonzero_without_clean_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_corrected_transcript(tmp_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        evaluate_semantic,
        "generate_with_timeout",
        lambda **kwargs: "not json",
    )
    monkeypatch.setattr(evaluate_semantic, "INTER_CHUNK_SLEEP_SECONDS", 0.0)
    monkeypatch.setattr(evaluate_semantic, "INTER_FILE_SLEEP_SECONDS", 0.0)

    result = evaluate_semantic.main([])

    report = tmp_path / "reports" / "semantic" / "talk.md"
    assert result == 1
    assert not report.exists()
