"""Tests YouTube metadata prompt rules and dry metadata flow."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import yt_metadata
from scripts.yt_metadata import get_system_instruction, process_files

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _blank_provider_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PROVIDER"] = "google"
    env["GEMINI_API_KEY"] = ""
    env["GEMINI_API_KEY_1"] = ""
    env["OPENROUTER_API_KEY"] = ""
    env["DEEPSEEK_API_KEY"] = ""
    return env


def test_default_prompt_requires_five_to_seven_sentences_and_no_bullets() -> None:
    instruction = get_system_instruction("en")

    assert "5-7 sentences" in instruction
    assert "no bullet" in instruction.lower()
    assert "bullet list" not in instruction.lower()


def test_no_work_exits_without_provider_backend_import(tmp_path: Path) -> None:
    (tmp_path / "output" / "transcribed" / "english").mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts import yt_metadata; yt_metadata.main()",
        ],
        cwd=tmp_path,
        env=_blank_provider_env(),
        capture_output=True,
        text=True,
        timeout=10,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Nothing to do." in output
    assert "No GEMINI_API_KEY" not in output


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
    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(yt_metadata, "generate_metadata", fake_generate_metadata)

    yt_metadata.main()

    assert seen_simple_english == [expected]


def test_pending_metadata_failure_returns_nonzero_and_writes_no_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript_dir = tmp_path / "output" / "transcribed" / "english"
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "talk.md").write_text("Transcript body.", encoding="utf-8")
    calls = 0

    def fail_generate_metadata(
        text: str,
        lang: str,
        speaker_name: str | None = None,
        *,
        simple_english_description: bool = False,
    ) -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider failed")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["yt_metadata.py", "--lang", "en"])
    monkeypatch.setattr(yt_metadata, "LLM_RETRY_DELAY_S", 0.0)
    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(yt_metadata, "generate_metadata", fail_generate_metadata)

    result = yt_metadata.main()

    review = tmp_path / "reviews" / "english_review.md"
    assert result == 1
    assert calls == 3
    assert "## Source: talk.md" not in review.read_text(encoding="utf-8")


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

    monkeypatch.setattr(yt_metadata, "get_playlist_overview", fail_playlist_fetch)

    process_files([transcript], "en", str(review), "english")


@pytest.mark.parametrize(
    "speaker_name",
    [
        "Ariyadhammika Bhikkhu",
    ],
)
def test_process_files_does_not_append_no_suffix_speaker_name_to_suggested_title(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    speaker_name: str,
) -> None:
    transcript = tmp_path / "talk.md"
    transcript.write_text("Transcript body.", encoding="utf-8")
    review = tmp_path / "review.md"

    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(
        yt_metadata,
        "generate_metadata",
        lambda text, lang, speaker_name=None, **kwargs: (
            "TITLE: Clear Seeing\nDESCRIPTION: A clear description.\nTAGS: #dhamma"
        ),
    )

    process_files(
        [transcript],
        "en",
        str(review),
        "english",
        speaker_name=speaker_name,
    )

    content = review.read_text(encoding="utf-8")
    assert "**Suggested Title:** Clear Seeing\n" in content
    assert f"Clear Seeing | {speaker_name}" not in content


@pytest.mark.parametrize(
    ("lang", "folder_name", "default_speaker"),
    [
        ("en", "english", "Bhikkhu Devamitta"),
        ("ru", "russian", "Бхиккху Дэвамитта"),
    ],
)
def test_main_appends_lang_default_speaker_to_suggested_title_when_name_omitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lang: str,
    folder_name: str,
    default_speaker: str,
) -> None:
    transcript_dir = tmp_path / "output" / "transcribed" / folder_name
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "talk.md").write_text("Transcript body.", encoding="utf-8")
    seen_speakers: list[str | None] = []

    def fake_generate_metadata(
        text: str,
        lang: str,
        speaker_name: str | None = None,
        *,
        simple_english_description: bool = False,
    ) -> str:
        seen_speakers.append(speaker_name)
        return "TITLE: Clear Seeing\nDESCRIPTION: A clear description.\nTAGS: #dhamma"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["yt_metadata.py", "--lang", lang])
    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(yt_metadata, "generate_metadata", fake_generate_metadata)

    yt_metadata.main()

    review = tmp_path / "reviews" / f"{folder_name}_review.md"
    content = review.read_text(encoding="utf-8")
    assert seen_speakers == [default_speaker]
    assert f"**Suggested Title:** Clear Seeing | {default_speaker}\n" in content


def test_process_files_appends_custom_speaker_name_to_suggested_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "talk.md"
    transcript.write_text("Transcript body.", encoding="utf-8")
    review = tmp_path / "review.md"

    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(
        yt_metadata,
        "generate_metadata",
        lambda text, lang, speaker_name=None, **kwargs: (
            "TITLE: Clear Seeing\nDESCRIPTION: A clear description.\nTAGS: #dhamma"
        ),
    )

    process_files(
        [transcript],
        "en",
        str(review),
        "english",
        speaker_name="Tissa Thero",
    )

    content = review.read_text(encoding="utf-8")
    assert "**Suggested Title:** Clear Seeing | Tissa Thero\n" in content


def test_process_files_writes_created_log_for_new_review_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "talk.md"
    transcript.write_text("Transcript body.", encoding="utf-8")
    review = tmp_path / "review.md"
    created_log = tmp_path / "created.log"

    monkeypatch.setattr(yt_metadata, "get_playlist_overview", lambda lang, dry_run: "")
    monkeypatch.setattr(yt_metadata, "load_nested_history", lambda path, lang: {})
    monkeypatch.setattr(
        yt_metadata,
        "generate_metadata",
        lambda text, lang, speaker_name=None, **kwargs: (
            "TITLE: Clear Seeing\nDESCRIPTION: A clear description.\nTAGS: #dhamma"
        ),
    )

    process_files(
        [transcript],
        "en",
        str(review),
        "english",
        created_log=created_log,
    )

    assert created_log.read_text(encoding="utf-8").splitlines() == [str(transcript)]


def test_dry_run_entry_does_not_append_no_suffix_speaker_name(tmp_path: Path) -> None:
    transcript = tmp_path / "dummy.md"
    transcript.write_text("Transcript body.", encoding="utf-8")
    review = tmp_path / "review.md"

    yt_metadata._write_dry_run_entry(
        review,
        transcript,
        "en",
        "video",
        "Ariyadhammika Bhikkhu",
    )

    content = review.read_text(encoding="utf-8")
    assert "**Suggested Title:** [DRY_RUN] dummy\n" in content
    assert "Ariyadhammika Bhikkhu" not in content


def test_process_files_removes_inferred_part_one_when_source_name_lacks_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "mindfulness talk.md"
    transcript.write_text("Transcript body.", encoding="utf-8")
    review = tmp_path / "review.md"

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
