"""Tests YouTube image generation work discovery before model access."""

import sys
import unicodedata
from pathlib import Path

import pytest

from scripts import yt_image_gen


def test_image_generation_does_not_probe_model_when_thumbnails_already_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    review_dir = tmp_path / "reviews"
    thumbnail_dir = tmp_path / "output" / "thumbnails" / "english"
    review_dir.mkdir()
    thumbnail_dir.mkdir(parents=True)
    (thumbnail_dir / "talk.jpg").write_bytes(b"existing image")
    (review_dir / "english_review.md").write_text(
        "\n".join(
            [
                "# Review",
                "",
                "---",
                "## Source: talk.md",
                "**Recording Date:** 01-06-2026",
                "**Approved:** yes",
                "**Suggested Title:** Existing Talk",
                "**Suggested Description:** Existing description.",
            ]
        ),
        encoding="utf-8",
    )

    def fail_key_probe() -> bool:
        raise AssertionError("model key probe should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_image_gen.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_image_gen, "get_working_key", fail_key_probe)
    monkeypatch.setattr(yt_image_gen, "load_nested_history", lambda path, lang: {})

    yt_image_gen.main()

    assert "Nothing to do." in capsys.readouterr().out


def test_image_generation_treats_decomposed_thumbnail_as_existing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stem = "2026-06-01 - Ёж и йога ānāpānasati"
    review_dir = tmp_path / "reviews"
    thumbnail_dir = tmp_path / "output" / "thumbnails" / "russian"
    review_dir.mkdir()
    thumbnail_dir.mkdir(parents=True)
    (thumbnail_dir / f"{unicodedata.normalize('NFD', stem)}.jpg").write_bytes(
        b"existing image"
    )
    (review_dir / "russian_review.md").write_text(
        "\n".join(
            [
                "# Review",
                "",
                "---",
                f"## Source: {stem}.md",
                "**Recording Date:** 01-06-2026",
                "**Approved:** yes",
                "**Suggested Title:** Ёж и йога",
                "**Suggested Description:** Existing description.",
            ]
        ),
        encoding="utf-8",
    )

    def fail_key_probe() -> bool:
        raise AssertionError("model key probe should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_image_gen.py", "--lang", "ru", "--folder", "russian"]
    )
    monkeypatch.setattr(yt_image_gen, "get_working_key", fail_key_probe)
    monkeypatch.setattr(yt_image_gen, "load_nested_history", lambda path, lang: {})

    yt_image_gen.main()

    assert "Nothing to do." in capsys.readouterr().out
