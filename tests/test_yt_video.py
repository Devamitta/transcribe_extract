"""Tests YouTube video creation source-log scoping."""

import sys
from pathlib import Path

import pytest

from scripts import yt_video


def _write_review(review: Path) -> None:
    review.write_text(
        "\n".join(
            [
                "# Review",
                "",
                "--- ",
                "## Source: current.md",
                "**Recording Date:** 01-06-2026",
                "**Approved:** yes",
                "**Suggested Title:** Current",
                "",
                "--- ",
                "## Source: backlog.md",
                "**Recording Date:** 02-06-2026",
                "**Approved:** yes",
                "**Suggested Title:** Backlog",
            ]
        ),
        encoding="utf-8",
    )


def test_video_creation_source_log_scopes_to_current_review_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for directory in (
        tmp_path / "reviews",
        tmp_path / "output/audio/english",
        tmp_path / "output/thumbnails/english",
        tmp_path / "output/video/english",
    ):
        directory.mkdir(parents=True)
    _write_review(tmp_path / "reviews/english_review.md")

    for stem in ("current", "backlog"):
        (tmp_path / f"output/audio/english/{stem}.mp3").write_bytes(b"audio")
        (tmp_path / f"output/thumbnails/english/{stem}.jpg").write_bytes(b"image")

    source_log = tmp_path / "export.log"
    source_log.write_text("current.mp4\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yt_video.py",
            "--lang",
            "en",
            "--folder",
            "english",
            "--dry-run",
            "--source-log",
            str(source_log),
        ],
    )

    yt_video.main()

    output = capsys.readouterr().out
    assert "current.mp3" in output
    assert "backlog.mp3" not in output
