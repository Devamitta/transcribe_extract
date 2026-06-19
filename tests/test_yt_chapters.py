"""Tests YouTube chapter stage work discovery before model access."""

import sys
import unicodedata
from pathlib import Path

import pytest

from scripts import yt_chapters


def _write_pending_chapter_fixture(tmp_path: Path) -> Path:
    transcript_dir = tmp_path / "output" / "transcribed" / "english"
    review_dir = tmp_path / "reviews"
    transcript_dir.mkdir(parents=True)
    review_dir.mkdir()
    transcript = "\n".join(
        f"[{index * 0.5:.1f}] Transcript paragraph {index}." for index in range(13)
    )
    (transcript_dir / "talk.md").write_text(transcript, encoding="utf-8")
    review_path = review_dir / "english_review.md"
    review_path.write_text(
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
    return review_path


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

    def fail_generation(*args: object, **kwargs: object) -> str:
        raise AssertionError("LLM generation should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_chapters.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_chapters, "generate_with_timeout", fail_generation)

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

    def fail_generation(*args: object, **kwargs: object) -> str:
        raise AssertionError("LLM generation should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_chapters.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_chapters, "generate_with_timeout", fail_generation)

    yt_chapters.main()

    assert "No timestamps found in talk.md, skipping" in capsys.readouterr().out


@pytest.mark.parametrize(
    "responses",
    [
        [RuntimeError("provider failed")] * 3,
        [""] * 3,
        ["not chapter output"] * 3,
        ["[0.0] Introduction\n[2.0] Second Topic"] * 3,
    ],
)
def test_chapters_llm_failures_exit_nonzero_without_writing_chapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str | RuntimeError],
) -> None:
    review_path = _write_pending_chapter_fixture(tmp_path)
    calls = 0

    def fake_generate_with_timeout(*args: object, **kwargs: object) -> str:
        nonlocal calls
        item = responses[calls]
        calls += 1
        if isinstance(item, RuntimeError):
            raise item
        return item

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_chapters.py", "--lang", "en", "--folder", "english"]
    )
    monkeypatch.setattr(yt_chapters, "LLM_RETRY_DELAY_S", 0.0)
    monkeypatch.setattr(
        yt_chapters, "generate_with_timeout", fake_generate_with_timeout
    )

    with pytest.raises(SystemExit) as exc_info:
        yt_chapters.main()

    assert exc_info.value.code == 1
    assert calls == 3
    assert "**Chapters:**" not in review_path.read_text(encoding="utf-8")


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

    def fail_generation(*args: object, **kwargs: object) -> str:
        raise AssertionError("LLM generation should not run")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["yt_chapters.py", "--lang", "ru", "--folder", "russian"]
    )
    monkeypatch.setattr(yt_chapters, "generate_with_timeout", fail_generation)

    yt_chapters.main()

    assert "Nothing to do." in capsys.readouterr().out
