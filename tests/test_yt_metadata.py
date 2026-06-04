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


def test_simple_english_rule_only_applies_when_requested_for_english() -> None:
    rule = "simple English sentences with plain vocabulary"

    assert rule not in get_system_instruction("en")
    assert rule in get_system_instruction(
        "en",
        speaker_name="Bhikkhu Devamitta",
        simple_english_description=True,
    )
    assert rule not in get_system_instruction(
        "en",
        speaker_name="Bhikkhu Devamitta",
    )
    assert rule not in get_system_instruction(
        "ru",
        simple_english_description=True,
    )


@pytest.mark.parametrize(
    ("cli_args", "expected"),
    [
        (["--lang", "en", "--folder", "english"], True),
        (["--folder", "english"], False),
        (["--lang", "en", "--folder", "english", "--name", "Tissa Thero"], False),
        (["--lang", "ru", "--folder", "english"], False),
    ],
)
def test_main_enables_simple_english_only_for_explicit_english_without_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli_args: list[str],
    expected: bool,
) -> None:
    transcript_dir = tmp_path / "output" / "transcribed" / "english"
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "talk.md").write_text("Transcript body.", encoding="utf-8")
    seen_simple_english: list[bool] = []

    def fake_generate_metadata(
        text: str,
        lang: str,
        speaker_name: str | None = None,
        *,
        simple_english_description: bool = False,
    ) -> str:
        seen_simple_english.append(simple_english_description)
        return "TITLE: Clear Seeing\nDESCRIPTION: A clear description.\nTAGS: #dhamma"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["yt_metadata.py", *cli_args])
    monkeypatch.setattr(yt_metadata, "get_working_key", lambda: "key")
    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(yt_metadata, "generate_metadata", fake_generate_metadata)

    yt_metadata.main()

    assert seen_simple_english == [expected]


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


def test_process_files_removes_inferred_part_one_when_source_name_lacks_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "mindfulness talk.md"
    transcript.write_text("Transcript body.", encoding="utf-8")
    review = tmp_path / "review.md"

    monkeypatch.setattr(yt_metadata, "get_working_key", lambda: "key")
    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(
        yt_metadata,
        "generate_metadata",
        lambda text, lang, speaker_name=None, **kwargs: (
            "TITLE: SATIPAṬṬHĀNA | Clear Seeing | Part 1\n"
            "DESCRIPTION: A clear description.\n"
            "TAGS: #dhamma"
        ),
    )

    process_files([transcript], "en", str(review), "english")

    content = review.read_text(encoding="utf-8")
    assert "**Suggested Title:** Clear Seeing\n" in content
    assert "Part 1" not in content


@pytest.mark.parametrize(
    "source_name",
    [
        "mindfulness lecture 1.md",
        "mindfulness part 1.md",
    ],
)
def test_process_files_keeps_part_one_when_source_name_mentions_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_name: str
) -> None:
    transcript = tmp_path / source_name
    transcript.write_text("Transcript body.", encoding="utf-8")
    review = tmp_path / "review.md"

    monkeypatch.setattr(yt_metadata, "get_working_key", lambda: "key")
    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(
        yt_metadata,
        "generate_metadata",
        lambda text, lang, speaker_name=None, **kwargs: (
            "TITLE: SATIPAṬṬHĀNA | Clear Seeing | Part 1\n"
            "DESCRIPTION: A clear description.\n"
            "TAGS: #dhamma"
        ),
    )

    process_files([transcript], "en", str(review), "english")

    content = review.read_text(encoding="utf-8")
    assert "**Suggested Title:** SATIPAṬṬHĀNA | Clear Seeing | Part 1\n" in content
