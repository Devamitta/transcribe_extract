"""Tests YouTube metadata prompt rules and dry metadata flow."""

from pathlib import Path

import pytest

from scripts import yt_metadata
from scripts.yt_metadata import get_system_instruction, process_files


def test_default_prompt_requires_five_to_seven_sentences_and_no_bullets() -> None:
    instruction = get_system_instruction("en")

    assert "5-7 sentences" in instruction
    assert "no bullet" in instruction.lower()
    assert "bullet list" not in instruction.lower()


def test_ariyadhammika_prompt_allows_up_to_fifteen_sentences_and_no_bullets() -> None:
    instruction = get_system_instruction("en", speaker_name="Ariyadhammika Bhikkhu")

    assert "up to 15 sentences" in instruction
    assert "no bullet" in instruction.lower()
    assert "bullet list" not in instruction.lower()


def test_process_files_does_not_fetch_playlists_when_all_sources_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "talk.md"
    transcript.write_text("Existing transcript.", encoding="utf-8")
    review = tmp_path / "review.md"
    review.write_text("## Source: talk.md\n", encoding="utf-8")

    def fail_playlist_fetch(lang: str, dry_run: bool) -> str:
        raise AssertionError("playlist overview should not be fetched")

    def fail_key_probe() -> str | None:
        raise AssertionError("LLM key probe should not run")

    monkeypatch.setattr(yt_metadata, "get_playlist_overview", fail_playlist_fetch)
    monkeypatch.setattr(yt_metadata, "get_working_key", fail_key_probe)

    process_files([transcript], "en", str(review), "english")
