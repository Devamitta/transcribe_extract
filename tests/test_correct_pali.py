"""Regression tests for the Pāli correction runner integration."""

import json
from pathlib import Path

import pytest

from scripts import batch, correct_pali
from tools.chunk_runner import EXIT_OK
from tools.pali import apply_overrides, get_pali_system_instruction
from tools.provider import CACHE_PREFIX


def test_pairs_applied_with_word_boundaries_and_logged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_file = tmp_path / "output" / "transcribed" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("Vinyan Vinyans unVinyan", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def generate(_chunk: str, _file_path: Path) -> str:
        return json.dumps([{"original": "Vinyan", "corrected": "viññāṇa"}])

    monkeypatch.setattr(correct_pali, "generate_pali_corrections", generate)
    monkeypatch.setattr(correct_pali, "INTER_CALL_PACING_SECONDS", 0)

    exit_code = correct_pali.main([])
    output_file = tmp_path / "output" / "corrected_pali" / "talk.md"
    report_file = tmp_path / "reports" / "pali_corrections" / "talk.json"

    assert exit_code == EXIT_OK
    assert output_file.read_text(encoding="utf-8") == "viññāṇa Vinyans unVinyan"
    assert json.loads(report_file.read_text(encoding="utf-8")) == [
        {
            "chunk_index": 0,
            "original": "Vinyan",
            "corrected": "viññāṇa",
            "count": 1,
        }
    ]
    assert not list(tmp_path.rglob(".status"))


def test_malformed_json_falls_back_to_original_without_failing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_file = tmp_path / "output" / "transcribed" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("unchanged text", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def generate(_chunk: str, _file_path: Path) -> str:
        return "not json"

    monkeypatch.setattr(correct_pali, "generate_pali_corrections", generate)
    monkeypatch.setattr(correct_pali, "INTER_CALL_PACING_SECONDS", 0)

    exit_code = correct_pali.main([])
    output_file = tmp_path / "output" / "corrected_pali" / "talk.md"
    report_file = tmp_path / "reports" / "pali_corrections" / "talk.json"

    assert exit_code == EXIT_OK
    assert output_file.read_text(encoding="utf-8") == "unchanged text"
    assert json.loads(report_file.read_text(encoding="utf-8")) == []
    assert not list(tmp_path.rglob(".status"))


def test_apply_overrides_corrects_unconditional_pairs_but_not_cook() -> None:
    corrected, applied = apply_overrides("winner cook Some vagina cookies")

    assert corrected == "Vinaya cook sampajañña kutis"
    assert {fix.original for fix in applied} == {"some vagina", "winner", "cookies"}


def test_generate_pali_corrections_sends_prepass_text_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_generate_with_timeout(**kwargs: str) -> str:
        captured["contents"] = kwargs["contents"]
        return "[]"

    monkeypatch.setattr(
        correct_pali,
        "generate_with_timeout",
        fake_generate_with_timeout,
    )

    correct_pali.generate_pali_corrections("winner", Path("talk.md"))

    assert captured["contents"] == f"{CACHE_PREFIX}Vinaya"


def test_pali_prompt_omits_prepass_overrides_but_keeps_context_rules() -> None:
    file_path = Path("output/transcribed/interview/talk.md")
    prompt = get_pali_system_instruction(file_path)

    assert "winner" not in prompt
    assert "epidemic" not in prompt
    assert "cookie" not in prompt
    assert "cook' -> 'kutī" in prompt
    assert "vagina" in prompt
    assert "Output ONLY a valid JSON array" in prompt
    assert "Viragadham Mikam" in prompt
    assert "PALI GLOSSARY" in prompt
    assert batch.TASK_CONFIG["pali"]["get_instruction"](file_path) == prompt
