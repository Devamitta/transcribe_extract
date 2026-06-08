"""Tests Google Drive upload folder selection behavior."""

import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from scripts import gdrive_upload
from scripts.gdrive_upload import resolve_drive_subfolder


class FakeDriveUploadRequest:
    pass


class FakeDriveFilesResource:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeDriveUploadRequest:
        self.calls.append(kwargs)
        return FakeDriveUploadRequest()


class FakeDrive:
    def __init__(self) -> None:
        self.files_resource = FakeDriveFilesResource()

    def files(self) -> FakeDriveFilesResource:
        return self.files_resource


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


def test_upload_file_enables_speed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "talk.mp4"
    media_path.write_bytes(b"video")
    drive = FakeDrive()
    captured: dict[str, Any] = {}

    def fake_execute_resumable_upload(
        request: Any, progress_label: str, **kwargs: Any
    ) -> dict[str, str]:
        captured["request"] = request
        captured["progress_label"] = progress_label
        captured["show_speed"] = kwargs.get("show_speed")
        return {"id": "drive_file_1"}

    monkeypatch.setattr(
        gdrive_upload,
        "execute_resumable_upload",
        fake_execute_resumable_upload,
    )

    file_id = gdrive_upload.upload_file(
        drive,
        media_path,
        "folder_1",
        "talk.mp4",
        "Description.",
        progress_label="    Drive video upload progress",
    )

    assert file_id == "drive_file_1"
    assert captured["progress_label"] == "    Drive video upload progress"
    assert captured["show_speed"] is True
    assert captured["request"] is not None


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


def test_dry_run_with_empty_files_log_does_not_fall_back_to_backlog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "reviews").mkdir()
    (tmp_path / "output/transcribed/english").mkdir(parents=True)
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
    files_log = tmp_path / "empty.log"
    files_log.write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GDRIVE_FOLDER_ID_EN", "root_folder")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gdrive_upload.py",
            "--lang",
            "en",
            "--folder",
            "english",
            "--dry-run",
            "--files-from-log",
            str(files_log),
        ],
    )

    gdrive_upload.main()

    output = capsys.readouterr().out
    assert "No new Drive uploads for this run." in output
    assert "video(s) queued for Google Drive upload." not in output


def test_real_run_prints_video_and_audio_sizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "reviews").mkdir()
    (tmp_path / "output/transcribed/english").mkdir(parents=True)
    (tmp_path / "output/audio/english").mkdir(parents=True)
    (tmp_path / "output/video/english").mkdir(parents=True)
    (tmp_path / "output/audio/english/talk.mp3").write_bytes(b"audio")
    (tmp_path / "output/video/english/talk.mp4").write_bytes(b"video")
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
        ["gdrive_upload.py", "--lang", "en", "--folder", "english"],
    )
    monkeypatch.setattr(gdrive_upload, "get_google_client", lambda *_args: FakeDrive())
    monkeypatch.setattr(
        gdrive_upload,
        "get_or_create_folder",
        lambda _drive, _parent_id, name: f"{name}_folder",
    )
    monkeypatch.setattr(
        gdrive_upload,
        "upload_file",
        lambda *_args, **_kwargs: "drive_file_1",
    )

    gdrive_upload.main()

    output = capsys.readouterr().out
    assert "Video size: 5 B" in output
    assert "Audio size: 5 B" in output


def test_dry_run_skips_uploaded_unicode_history_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    filename = "2026-06-01 - Ёж и йога ānāpānasati.mp4"
    stem = Path(filename).stem
    (tmp_path / "reviews").mkdir()
    (tmp_path / "output/transcribed/russian").mkdir(parents=True)
    (tmp_path / "output/audio/russian").mkdir(parents=True)
    (tmp_path / "output/video/russian").mkdir(parents=True)
    (tmp_path / f"output/audio/russian/{stem}.mp3").write_bytes(b"stub")
    (tmp_path / f"output/video/russian/{filename}").write_bytes(b"stub")
    (tmp_path / "reviews/russian_review.md").write_text(
        "\n".join(
            [
                "# Russian Audio Metadata Review",
                "--- ",
                f"## Source: {stem}.md",
                "**Recording Date:** 01-06-2026",
                "**Publish Date:**",
                "**Approved:** yes",
                "**Media:** video",
                "**Channel Playlist Overview:** Meditation",
                "**Selected Playlist:** Meditation",
                "**Suggested Title:** Ёж и йога ānāpānasati",
                "**Suggested Description:** Description.",
                "",
                "**Suggested Tags:** #dhamma",
            ]
        ),
        encoding="utf-8",
    )
    history_key = unicodedata.normalize("NFD", f"Meditation/{filename}")
    (tmp_path / "output/gdrive_history.json").write_text(
        json.dumps(
            {
                "ru": {
                    "video": {
                        history_key: {
                            "status": "uploaded",
                            "platform_id": "drive_video_1",
                        }
                    },
                    "audio": {},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GDRIVE_FOLDER_ID_RU", "root_folder")
    monkeypatch.setattr(
        sys,
        "argv",
        ["gdrive_upload.py", "--lang", "ru", "--folder", "russian", "--dry-run"],
    )

    gdrive_upload.main()

    output = capsys.readouterr().out
    assert "Everything already uploaded." in output
    assert "video(s) queued for Google Drive upload." not in output
