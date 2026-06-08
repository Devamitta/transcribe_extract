"""Tests YouTube chapter stage work discovery before model access."""

import sys
import unicodedata
from pathlib import Path

import pytest

from scripts import yt_chapters


def test_chapters_does_not_probe_model_when_nothing_is_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript_dir = tmp_path / "output" / "transcribed" / "english"
    review_dir = tmp_path / "reviews"
    transcript_dir.mkdir(parents=True)
    review_dir.mkdir()
    (transcript_dir / "talk.md").write_text(
        "[0.0] Existing transcript.", encoding="utf-8"
    )
    (review_dir / "english_review.md").write_text(
        "\n".join(
            [
                "# Review",
                "",
                "---",
                "## Source: talk.md",
                "**Suggested Tags:** #dhamma",
                "**Chapters:**",
                "[00:00] Introduction",
            ]
        ),
        encoding="utf-8",
    )

    def fail_key_probe() -> bool:
        raise AssertionError("model key probe should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_chapters.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_chapters, "get_working_key", fail_key_probe)

    yt_chapters.main()

    assert "Nothing to do." in capsys.readouterr().out


def test_chapters_does_not_probe_model_for_locally_skipped_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript_dir = tmp_path / "output" / "transcribed" / "english"
    review_dir = tmp_path / "reviews"
    transcript_dir.mkdir(parents=True)
    review_dir.mkdir()
    (transcript_dir / "talk.md").write_text(
        "Transcript without timestamp anchors.", encoding="utf-8"
    )
    (review_dir / "english_review.md").write_text(
        "\n".join(
            [
                "# Review",
                "",
                "---",
                "## Source: talk.md",
                "**Suggested Tags:** #dhamma",
            ]
        ),
        encoding="utf-8",
    )

    def fail_key_probe() -> bool:
        raise AssertionError("model key probe should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_chapters.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_chapters, "get_working_key", fail_key_probe)

    yt_chapters.main()

    assert "No timestamps found in talk.md, skipping" in capsys.readouterr().out


def test_chapters_matches_decomposed_review_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stem = "2026-06-01 - Ёж и йога ānāpānasati"
    transcript_dir = tmp_path / "output" / "transcribed" / "russian"
    review_dir = tmp_path / "reviews"
    transcript_dir.mkdir(parents=True)
    review_dir.mkdir()
    (transcript_dir / f"{stem}.md").write_text(
        "[0.0] Existing transcript.", encoding="utf-8"
    )
    decomposed_source = unicodedata.normalize("NFD", f"{stem}.md")
    (review_dir / "russian_review.md").write_text(
        "\n".join(
            [
                "# Review",
                "",
                "---",
                f"## Source: {decomposed_source}",
                "**Suggested Tags:** #dhamma",
                "**Chapters:**",
                "[00:00] Introduction",
            ]
        ),
        encoding="utf-8",
    )

    def fail_key_probe() -> bool:
        raise AssertionError("model key probe should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_chapters.py", "--lang", "ru", "--folder", "russian"]
    )
    monkeypatch.setattr(yt_chapters, "get_working_key", fail_key_probe)

    yt_chapters.main()

    assert "Nothing to do." in capsys.readouterr().out
