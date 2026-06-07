"""Tests YouTube upload playlist selection and history behavior."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import yt_upload
from scripts.yt_upload import add_video_to_selected_playlists


class FakeInsertRequest:
    def execute(self) -> dict[str, str]:
        return {}


class FakePlaylistItemsResource:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def insert(self, **kwargs: Any) -> FakeInsertRequest:
        self.calls.append(kwargs)
        return FakeInsertRequest()


class FakeYouTube:
    def __init__(self) -> None:
        self.playlist_items_resource = FakePlaylistItemsResource()

    def playlistItems(self) -> FakePlaylistItemsResource:
        return self.playlist_items_resource


def test_add_video_to_selected_playlists_continues_when_one_is_missing() -> None:
    youtube = FakeYouTube()

    added = add_video_to_selected_playlists(
        youtube,
        "video_1",
        ["Meditation", "Missing"],
        {"Meditation": "playlist_1"},
        "talk.mp4",
    )

    assert added == ["Meditation"]
    assert youtube.playlist_items_resource.calls == [
        {
            "part": "snippet",
            "body": {
                "snippet": {
                    "playlistId": "playlist_1",
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": "video_1",
                    },
                }
            },
        }
    ]


def test_upload_skips_nested_history_key_by_final_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "reviews").mkdir()
    (tmp_path / "output/video/english").mkdir(parents=True)
    (tmp_path / "output").mkdir(exist_ok=True)
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
    (tmp_path / "output/youtube_history.json").write_text(
        json.dumps(
            {
                "en": {
                    "english/talk.mp4": {
                        "status": "uploaded",
                        "platform_id": "video_1",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["yt_upload.py", "--lang", "en", "--dry-run", "--batch-size", "0"],
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    yt_upload.main()

    output = capsys.readouterr().out
    assert "Everything already uploaded." in output
    assert "video(s) queued for YouTube upload." not in output


def test_upload_with_empty_files_log_does_not_fall_back_to_backlog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "reviews").mkdir()
    (tmp_path / "output/video/english").mkdir(parents=True)
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
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yt_upload.py",
            "--lang",
            "en",
            "--dry-run",
            "--batch-size",
            "0",
            "--files-from-log",
            str(files_log),
        ],
    )

    yt_upload.main()

    output = capsys.readouterr().out
    assert "No new uploads for this run." in output
    assert "video(s) queued for YouTube upload." not in output
