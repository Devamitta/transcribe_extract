"""Tests shared YouTube uploader parsing and playlist helpers."""

from pathlib import Path

from typing import Any

from tools.uploader_common import (
    execute_resumable_upload,
    is_uploaded_in_history,
    list_channel_playlists,
    parse_review,
)


class FakePlaylistListRequest:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def execute(self) -> dict[str, Any]:
        return self.response


class FakePlaylistsResource:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def list(self, **kwargs: Any) -> FakePlaylistListRequest:
        self.calls.append(kwargs)
        if kwargs.get("pageToken") == "next":
            return FakePlaylistListRequest(
                {
                    "items": [
                        {"id": "pl_3", "snippet": {"title": " Retreat "}},
                    ]
                }
            )
        return FakePlaylistListRequest(
            {
                "items": [
                    {"id": "pl_1", "snippet": {"title": "Meditation"}},
                    {"id": "pl_2", "snippet": {"title": "Personal"}},
                ],
                "nextPageToken": "next",
            }
        )


class FakeYouTube:
    def __init__(self) -> None:
        self.playlists_resource = FakePlaylistsResource()

    def playlists(self) -> FakePlaylistsResource:
        return self.playlists_resource


class FakeUploadStatus:
    def __init__(self, value: float) -> None:
        self.value = value

    def progress(self) -> float:
        return self.value


class FakeResumableUploadRequest:
    def __init__(
        self, chunks: list[tuple[float | None, dict[str, Any] | None]]
    ) -> None:
        self.chunks = chunks
        self.index = 0

    def next_chunk(self) -> tuple[FakeUploadStatus | None, dict[str, Any] | None]:
        progress, response = self.chunks[self.index]
        self.index += 1
        status = FakeUploadStatus(progress) if progress is not None else None
        return status, response


def test_execute_resumable_upload_reports_percentages_and_returns_response() -> None:
    request = FakeResumableUploadRequest(
        [
            (0.1, None),
            (0.1, None),
            (0.5, None),
            (None, {"id": "uploaded_1"}),
        ]
    )
    messages: list[str] = []

    response = execute_resumable_upload(request, "Upload progress", messages.append)

    assert response == {"id": "uploaded_1"}
    assert messages == [
        "Upload progress: 10%",
        "Upload progress: 50%",
        "Upload progress: 100%",
    ]


def test_parse_review_reads_playlist_fields(tmp_path: Path) -> None:
    review_path = tmp_path / "review.md"
    review_path.write_text(
        "\n".join(
            [
                "# Review",
                "",
                "--- ",
                "## Source: talk.md",
                "**Recording Date:** 29-05-2026",
                "**Publish Date:**",
                "**Approved:** yes",
                "**Media:** video",
                "**Channel Playlist Overview:** Meditation, Personal",
                "**Selected Playlist:** Meditation",
                "**Suggested Title:** Test Title",
                "**Suggested Description:** Test description.",
                "",
                "**Suggested Tags:** #dhamma",
            ]
        ),
        encoding="utf-8",
    )

    parsed = parse_review(review_path)

    assert parsed["talk"]["channel_playlist_overview"] == "Meditation, Personal"
    assert parsed["talk"]["selected_playlists"] == ["Meditation"]


def test_parse_review_keeps_blank_selected_playlist_empty(tmp_path: Path) -> None:
    review_path = tmp_path / "review.md"
    review_path.write_text(
        "\n".join(
            [
                "# Review",
                "",
                "--- ",
                "## Source: talk.md",
                "**Recording Date:** 29-05-2026",
                "**Publish Date:**",
                "**Approved:** yes",
                "**Media:** video",
                "**Channel Playlist Overview:** Meditation",
                "**Selected Playlist:**",
                "**Suggested Title:** Test Title",
                "**Suggested Description:** Test description.",
                "",
                "**Suggested Tags:** #dhamma",
            ]
        ),
        encoding="utf-8",
    )

    parsed = parse_review(review_path)

    assert parsed["talk"]["selected_playlists"] == []


def test_parse_review_splits_selected_playlists_on_commas_and_semicolons(
    tmp_path: Path,
) -> None:
    cases = {
        "Meditation, Personal": ["Meditation", "Personal"],
        "Meditation; Personal": ["Meditation", "Personal"],
        "Meditation, Personal; Retreat": ["Meditation", "Personal", "Retreat"],
    }

    for raw_playlists, expected in cases.items():
        review_path = tmp_path / f"{raw_playlists.replace(' ', '_')}.md"
        review_path.write_text(
            "\n".join(
                [
                    "# Review",
                    "",
                    "--- ",
                    "## Source: talk.md",
                    "**Recording Date:** 29-05-2026",
                    "**Publish Date:**",
                    "**Approved:** yes",
                    "**Media:** video",
                    "**Channel Playlist Overview:** Meditation, Personal, Retreat",
                    f"**Selected Playlist:** {raw_playlists}",
                    "**Suggested Title:** Test Title",
                    "**Suggested Description:** Test description.",
                    "",
                    "**Suggested Tags:** #dhamma",
                ]
            ),
            encoding="utf-8",
        )

        parsed = parse_review(review_path)

        assert parsed["talk"]["selected_playlists"] == expected


def test_list_channel_playlists_handles_pagination_and_trims_titles() -> None:
    youtube = FakeYouTube()

    playlists = list_channel_playlists(youtube)

    assert playlists == {
        "Meditation": "pl_1",
        "Personal": "pl_2",
        "Retreat": "pl_3",
    }
    assert youtube.playlists_resource.calls == [
        {
            "part": "snippet",
            "mine": True,
            "maxResults": 50,
            "pageToken": None,
        },
        {
            "part": "snippet",
            "mine": True,
            "maxResults": 50,
            "pageToken": "next",
        },
    ]


def test_is_uploaded_in_history_matches_exact_final_names_and_nested_keys() -> None:
    history = {
        "english/2026-05-29 - Talk.mp4": {"status": "uploaded"},
        "2026-05-30 - Other.mp4": {"status": "failed"},
    }

    assert is_uploaded_in_history(history, "2026-05-29 - Talk.mp4")
    assert not is_uploaded_in_history(history, "2026-05-30 - Other.mp4")
    assert not is_uploaded_in_history(history, "Talk.mp4")
