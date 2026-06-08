"""Tests scripts.yt_export title synchronization behavior."""

import sys
import unicodedata
from pathlib import Path

import pytest

from scripts import yt_export


def _write_review(review_path: Path, entries: list[tuple[str, str, str]]) -> None:
    lines = ["# English Audio Metadata Review"]
    for source_name, recording_date, title in entries:
        lines.extend(
            [
                "",
                "---",
                f"## Source: {source_name}",
                f"**Recording Date:** {recording_date}",
                "**Publish Date:**",
                "**Approved:** yes",
                "**Media:** audio",
                "**Channel Playlist Overview:** Meditation",
                "**Selected Playlist:** Meditation",
                f"**Suggested Title:** {title}",
                "**Suggested Description:** Description.",
                "",
                "**Suggested Tags:** #dhamma",
            ]
        )

    review_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def test_rename_step_source_log_scopes_renames_to_current_sources(
    tmp_path: Path,
) -> None:
    review = tmp_path / "reviews" / "english_review.md"
    transcript_dir = tmp_path / "output" / "transcribed" / "english"
    audio_dir = tmp_path / "output" / "audio" / "english"
    video_dir = tmp_path / "output" / "video" / "english"
    for directory in (review.parent, transcript_dir, audio_dir, video_dir):
        directory.mkdir(parents=True)
    _write_review(
        review,
        [
            ("current.md", "01-06-2026", "Current Title"),
            ("backlog.md", "02-06-2026", "Backlog Title"),
        ],
    )

    for stem in ("current", "backlog"):
        (transcript_dir / f"{stem}.md").write_text("Transcript.", encoding="utf-8")
        (audio_dir / f"{stem}.mp3").write_bytes(b"audio")
        (video_dir / f"{stem}.mp4").write_bytes(b"video")

    source_log = tmp_path / "metadata.log"
    source_log.write_text(str(transcript_dir / "current.md") + "\n", encoding="utf-8")

    renamed = yt_export.rename_step(
        review,
        transcript_dir,
        audio_dir,
        video_dir,
        video_mode=True,
        dry_run=False,
        source_filter=yt_export.read_source_filter(source_log),
    )

    assert renamed == [video_dir / "2026-06-01 - Current Title.mp4"]
    assert (transcript_dir / "2026-06-01 - Current Title.md").exists()
    assert (video_dir / "2026-06-01 - Current Title.mp4").exists()
    assert (transcript_dir / "backlog.md").exists()
    assert (video_dir / "backlog.mp4").exists()

    content = review.read_text(encoding="utf-8")
    assert "## Source: 2026-06-01 - Current Title.md" in content
    assert "## Source: backlog.md" in content


def test_sync_titles_renames_files_and_skips_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_stem = "2026-01-03 - Old Title"
    new_stem = "2026-01-03 - New Title"
    review_path = tmp_path / "reviews" / "english_review.md"
    transcript_dir = tmp_path / "output" / "transcribed" / "english"
    audio_dir = tmp_path / "output" / "audio" / "english"
    video_dir = tmp_path / "output" / "video" / "english"
    thumbnail_dir = tmp_path / "output" / "thumbnails" / "english"
    cover_dir = tmp_path / "output" / "covers" / "english"
    created_log = tmp_path / "created.log"

    for directory in [
        review_path.parent,
        transcript_dir,
        audio_dir,
        video_dir,
        thumbnail_dir,
        cover_dir,
    ]:
        directory.mkdir(parents=True)

    _write_review(review_path, [(f"{old_stem}.md", "03-01-2026", "New Title")])
    (transcript_dir / f"{old_stem}.md").write_text("Transcript.", encoding="utf-8")
    (audio_dir / f"{old_stem}.mp3").write_bytes(b"audio")
    (thumbnail_dir / f"{old_stem}.jpg").write_bytes(b"thumbnail")
    (cover_dir / f"{old_stem}.jpg").write_bytes(b"cover")
    created_log.write_text("stale.mp4\n", encoding="utf-8")

    def fail_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ffmpeg should not run during title sync")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(yt_export.subprocess, "run", fail_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yt_export.py",
            "--lang",
            "en",
            "--folder",
            "english",
            "--sync-titles",
            "--created-log",
            str(created_log),
        ],
    )

    yt_export.main()

    assert not (transcript_dir / f"{old_stem}.md").exists()
    assert not (audio_dir / f"{old_stem}.mp3").exists()
    assert not (thumbnail_dir / f"{old_stem}.jpg").exists()
    assert not (cover_dir / f"{old_stem}.jpg").exists()
    assert (transcript_dir / f"{new_stem}.md").exists()
    assert (audio_dir / f"{new_stem}.mp3").exists()
    assert (thumbnail_dir / f"{new_stem}.jpg").exists()
    assert (cover_dir / f"{new_stem}.jpg").exists()
    assert f"## Source: {new_stem}.md" in review_path.read_text(encoding="utf-8")
    assert created_log.read_text(encoding="utf-8") == (
        f"output/video/english/{new_stem}.mp4\n"
    )


def test_rename_step_skips_uploaded_unicode_final_name_before_rename(
    tmp_path: Path,
) -> None:
    old_stem = "source"
    final_stem = "2026-06-01 - Ёж и йога ānāpānasati"
    review = tmp_path / "reviews" / "russian_review.md"
    transcript_dir = tmp_path / "output" / "transcribed" / "russian"
    audio_dir = tmp_path / "output" / "audio" / "russian"
    video_dir = tmp_path / "output" / "video" / "russian"
    for directory in (review.parent, transcript_dir, audio_dir, video_dir):
        directory.mkdir(parents=True)
    _write_review(review, [(f"{old_stem}.md", "01-06-2026", "Ёж и йога ānāpānasati")])
    (transcript_dir / f"{old_stem}.md").write_text("Transcript.", encoding="utf-8")
    (audio_dir / f"{old_stem}.mp3").write_bytes(b"audio")
    (video_dir / f"{old_stem}.mp4").write_bytes(b"video")
    history = {
        unicodedata.normalize("NFD", f"{final_stem}.mp4"): {"status": "uploaded"}
    }

    renamed = yt_export.rename_step(
        review,
        transcript_dir,
        audio_dir,
        video_dir,
        video_mode=False,
        dry_run=False,
        uploaded_history=history,
    )

    assert renamed == []
    assert (transcript_dir / f"{old_stem}.md").exists()
    assert not (transcript_dir / f"{final_stem}.md").exists()
    assert f"## Source: {old_stem}.md" in review.read_text(encoding="utf-8")
