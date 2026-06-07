"""Tests YouTube export title syncing and source-log scoping."""

from pathlib import Path

from scripts.yt_export import rename_step
from tools.source_scope import read_source_filter


def _write_review(review: Path) -> None:
    review.write_text(
        "\n".join(
            [
                "# Review",
                "",
                "--- ",
                "## Source: current.md",
                "**Recording Date:** 01-06-2026",
                "**Publish Date:**",
                "**Approved:** yes",
                "**Media:** video",
                "**Suggested Title:** Current Title",
                "**Suggested Description:** Description.",
                "",
                "**Suggested Tags:** #dhamma",
                "",
                "--- ",
                "## Source: backlog.md",
                "**Recording Date:** 02-06-2026",
                "**Publish Date:**",
                "**Approved:** yes",
                "**Media:** video",
                "**Suggested Title:** Backlog Title",
                "**Suggested Description:** Description.",
                "",
                "**Suggested Tags:** #dhamma",
            ]
        ),
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
    _write_review(review)

    for stem in ("current", "backlog"):
        (transcript_dir / f"{stem}.md").write_text("Transcript.", encoding="utf-8")
        (audio_dir / f"{stem}.mp3").write_bytes(b"audio")
        (video_dir / f"{stem}.mp4").write_bytes(b"video")

    source_log = tmp_path / "metadata.log"
    source_log.write_text(str(transcript_dir / "current.md") + "\n", encoding="utf-8")

    renamed = rename_step(
        review,
        transcript_dir,
        audio_dir,
        video_dir,
        video_mode=True,
        dry_run=False,
        source_filter=read_source_filter(source_log),
    )

    assert renamed == [video_dir / "2026-06-01 - Current Title.mp4"]
    assert (transcript_dir / "2026-06-01 - Current Title.md").exists()
    assert (video_dir / "2026-06-01 - Current Title.mp4").exists()
    assert (transcript_dir / "backlog.md").exists()
    assert (video_dir / "backlog.mp4").exists()

    content = review.read_text(encoding="utf-8")
    assert "## Source: 2026-06-01 - Current Title.md" in content
    assert "## Source: backlog.md" in content
