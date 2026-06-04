"""Tests Google Drive upload folder selection behavior."""

import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import gdrive_upload
from scripts.gdrive_upload import resolve_drive_subfolder


def test_resolve_drive_subfolder_uses_single_selected_playlist() -> None:
    meta: dict[str, Any] = {"selected_playlists": ["Meditation"]}

    assert resolve_drive_subfolder(meta) == "Meditation"


def test_resolve_drive_subfolder_prompts_for_multiple_selected_playlists() -> None:
    meta: dict[str, Any] = {"selected_playlists": ["Meditation", "Personal"]}

    assert (
        resolve_drive_subfolder(meta, "talk.mp4", input_func=lambda _: "2")
        == "Personal"
    )


def test_resolve_drive_subfolder_ignores_playlist_overview_when_blank() -> None:
    meta: dict[str, Any] = {
        "selected_playlists": [],
        "channel_playlist_overview": "Meditation",
    }

    assert resolve_drive_subfolder(meta) is None


def test_resolve_drive_subfolder_returns_none_without_selected_playlist() -> None:
    meta: dict[str, Any] = {
        "selected_playlists": [],
        "channel_playlist_overview": "",
    }

    assert resolve_drive_subfolder(meta) is None


def test_dry_run_uses_selected_playlist_as_drive_subfolder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "reviews").mkdir()
    (tmp_path / "output/audio/english").mkdir(parents=True)
    (tmp_path / "output/video/english").mkdir(parents=True)
    (tmp_path / "output/audio/english/talk.mp3").write_bytes(b"stub")
    (tmp_path / "output/video/english/talk.mp4").write_bytes(b"stub")
    (tmp_path / "reviews/english_review.md").write_text(
        "\n".join(
            [
                "# English Audio Metadata Review",
                "--- ",
                "## Source: talk.md",
                "**Recording Date:** 29-05-2026",
                "**Publish Date:**",
                "**Approved:** yes",
                "**Media:** video",
                "**Channel Playlist Overview:** Meditation",
                "**Selected Playlist:** Meditation",
                "**Suggested Title:** Talk",
                "**Suggested Description:** Description.",
                "",
                "**Suggested Tags:** #dhamma",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GDRIVE_FOLDER_ID_EN", "root_folder")
    monkeypatch.setattr(
        sys,
        "argv",
        ["gdrive_upload.py", "--lang", "en", "--folder", "english", "--dry-run"],
    )

    gdrive_upload.main()

    output = capsys.readouterr().out
    assert "Folder:      video/Meditation/talk.mp4" in output
    assert "Audio:       audio/Meditation/talk.mp3" in output


def test_dry_run_uses_base_folders_when_selected_playlist_is_blank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "reviews").mkdir()
    (tmp_path / "output/audio/english").mkdir(parents=True)
    (tmp_path / "output/video/english").mkdir(parents=True)
    (tmp_path / "output/audio/english/talk.mp3").write_bytes(b"stub")
    (tmp_path / "output/video/english/talk.mp4").write_bytes(b"stub")
    (tmp_path / "reviews/english_review.md").write_text(
        "\n".join(
            [
                "# English Audio Metadata Review",
                "--- ",
                "## Source: talk.md",
                "**Recording Date:** 29-05-2026",
                "**Publish Date:**",
                "**Approved:** yes",
                "**Media:** video",
                "**Channel Playlist Overview:** Meditation",
                "**Selected Playlist:**",
                "**Suggested Title:** Talk",
                "**Suggested Description:** Description.",
                "",
                "**Suggested Tags:** #dhamma",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GDRIVE_FOLDER_ID_EN", "root_folder")
    monkeypatch.setattr(
        sys,
        "argv",
        ["gdrive_upload.py", "--lang", "en", "--folder", "english", "--dry-run"],
    )

    gdrive_upload.main()

    output = capsys.readouterr().out
    assert "Folder:      video/talk.mp4" in output
    assert "Audio:       audio/talk.mp3" in output
    assert "video/Meditation/talk.mp4" not in output
    assert "audio/Meditation/talk.mp3" not in output
