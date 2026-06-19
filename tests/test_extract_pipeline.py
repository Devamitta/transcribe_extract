"""Regression tests for the extracted-Dhamma runner integration."""

import json
from pathlib import Path

import pytest

from scripts import extract_dhamma
from tools.chunk_runner import EXIT_OK, EXIT_PARTIAL
from tools.incremental import get_temp_path


def test_failed_chunk_leaves_temp_and_writes_no_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_file = tmp_path / "output" / "corrected_pali" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("bad chunk", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def fail_generate(_text: str, _file_path: Path | None = None) -> str:
        raise RuntimeError("provider failed")

    monkeypatch.setattr(extract_dhamma, "extract_dhamma_points", fail_generate)
    monkeypatch.setattr(extract_dhamma, "INTER_CALL_PACING_SECONDS", 0)

    exit_code = extract_dhamma.main([])
    output_file = tmp_path / "output" / "extracted" / "talk.md"
    temp_file = get_temp_path(output_file)

    assert exit_code == EXIT_PARTIAL
    assert not output_file.exists()
    assert json.loads(temp_file.read_text(encoding="utf-8")) == [None]


def test_no_points_chunks_are_excluded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_file = tmp_path / "output" / "corrected_pali" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("skip|keep", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(extract_dhamma, "build_chunks", lambda text: text.split("|"))

    def generate(text: str, _file_path: Path | None = None) -> str:
        if text == "skip":
            return "NO_POINTS"
        return "## [dhamma]\nTeaching content."

    monkeypatch.setattr(extract_dhamma, "extract_dhamma_points", generate)
    monkeypatch.setattr(extract_dhamma, "INTER_CALL_PACING_SECONDS", 0)

    exit_code = extract_dhamma.main([])
    output_file = tmp_path / "output" / "extracted" / "talk.md"

    assert exit_code == EXIT_OK
    assert output_file.read_text(encoding="utf-8") == "## [dhamma]\nTeaching content."


def test_low_output_ratio_prints_warning_but_writes_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_file = tmp_path / "output" / "corrected_pali" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text(
        "one two three four five six seven eight nine ten", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    def generate(_text: str, _file_path: Path | None = None) -> str:
        return "short"

    monkeypatch.setattr(extract_dhamma, "extract_dhamma_points", generate)
    monkeypatch.setattr(extract_dhamma, "INTER_CALL_PACING_SECONDS", 0)

    exit_code = extract_dhamma.main([])
    output_file = tmp_path / "output" / "extracted" / "talk.md"
    captured = capsys.readouterr()

    assert exit_code == EXIT_OK
    assert output_file.read_text(encoding="utf-8") == "short"
    assert "below 50%" in captured.out
    assert "low ratio warnings" in captured.out
