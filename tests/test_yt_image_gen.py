"""Tests YouTube image generation work discovery before model access."""

import sys
import unicodedata
from pathlib import Path

import pytest

from scripts import yt_image_gen


def _write_approved_review(tmp_path: Path) -> None:
    review_dir = tmp_path / "reviews"
    review_dir.mkdir()
    (review_dir / "english_review.md").write_text(
        "\n".join(
            [
                "# Review",
                "",
                "---",
                "## Source: talk.md",
                "**Recording Date:** 01-06-2026",
                "**Approved:** yes",
                "**Suggested Title:** Required Talk",
                "**Suggested Description:** Required description.",
            ]
        ),
        encoding="utf-8",
    )


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

    def fail_generation(*args: object, **kwargs: object) -> str:
        raise AssertionError("LLM generation should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_image_gen.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_image_gen, "generate_content", fail_generation)
    monkeypatch.setattr(yt_image_gen, "load_nested_history", lambda path, lang: {})

    yt_image_gen.main()

    assert "Nothing to do." in capsys.readouterr().out


def test_prompt_generation_failure_returns_nonzero_without_generic_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_approved_review(tmp_path)
    calls = 0

    def fail_prompt(*args: object, **kwargs: object) -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider failed")

    def fail_image(*args: object, **kwargs: object) -> None:
        raise AssertionError("image generation should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_image_gen.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_image_gen, "LLM_RETRY_DELAY_S", 0.0)
    monkeypatch.setattr(yt_image_gen, "generate_content", fail_prompt)
    monkeypatch.setattr(yt_image_gen, "generate_image", fail_image)
    monkeypatch.setattr(yt_image_gen, "load_nested_history", lambda path, lang: {})

    result = yt_image_gen.main()

    assert result == 1
    assert calls == 3
    assert not (tmp_path / "output" / "thumbnails" / "english" / "talk.jpg").exists()


def test_image_generation_failure_returns_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_approved_review(tmp_path)
    image_calls = 0

    def fail_image(prompt: str, out_path: Path) -> None:
        nonlocal image_calls
        image_calls += 1
        raise RuntimeError("image provider failed")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_image_gen.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_image_gen, "LLM_RETRY_DELAY_S", 0.0)
    monkeypatch.setattr(
        yt_image_gen,
        "generate_content",
        lambda *args, **kwargs: "A specific forest monastery scene.",
    )
    monkeypatch.setattr(yt_image_gen, "generate_image", fail_image)
    monkeypatch.setattr(yt_image_gen, "load_nested_history", lambda path, lang: {})

    result = yt_image_gen.main()

    assert result == 1
    assert image_calls == 3
    assert not (tmp_path / "output" / "thumbnails" / "english" / "talk.jpg").exists()


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

    def fail_generation(*args: object, **kwargs: object) -> str:
        raise AssertionError("LLM generation should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_image_gen.py", "--lang", "ru", "--folder", "russian"]
    )
    monkeypatch.setattr(yt_image_gen, "generate_content", fail_generation)
    monkeypatch.setattr(yt_image_gen, "load_nested_history", lambda path, lang: {})

    yt_image_gen.main()

    assert "Nothing to do." in capsys.readouterr().out
