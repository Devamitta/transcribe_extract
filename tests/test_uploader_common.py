"""Tests shared YouTube uploader parsing and playlist helpers."""

from pathlib import Path
import unicodedata

from typing import Any

from tools.uploader_common import (
    execute_resumable_upload,
    find_path_by_normalized_name,
    format_file_size,
    is_uploaded_in_history,
    is_uploaded_key_in_history,
    list_channel_playlists,
    make_history_key,
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
    def __init__(self, value: float, total_size: int = 100) -> None:
        self.value = value
        self.total_size: int | None = total_size
        self.resumable_progress = int(value * total_size)

    def progress(self) -> float:
        return self.value


class FakeResumableUploadRequest:
    def __init__(
        self,
        chunks: list[tuple[float | None, dict[str, Any] | None]],
        total_size: int = 100,
    ) -> None:
        self.chunks = chunks
        self.total_size = total_size
        self.index = 0

    def next_chunk(self) -> tuple[FakeUploadStatus | None, dict[str, Any] | None]:
        progress, response = self.chunks[self.index]
        self.index += 1
        status = (
            FakeUploadStatus(progress, self.total_size)
            if progress is not None
            else None
        )
        return status, response


class FakeClock:
    def __init__(self, ticks: list[float]) -> None:
        self.ticks = ticks
        self.index = 0

    def __call__(self) -> float:
        tick = self.ticks[self.index]
        self.index += 1
        return tick


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


def test_execute_resumable_upload_reports_dynamic_progress_with_speed() -> None:
    total_size = 100 * 1024 * 1024
    request = FakeResumableUploadRequest(
        [
            (0.32, None),
            (0.64, None),
            (None, {"id": "uploaded_1"}),
        ],
        total_size=total_size,
    )
    messages: list[str] = []

    response = execute_resumable_upload(
        request,
        "Video upload progress",
        messages.append,
        show_speed=True,
        clock=FakeClock([0.0, 2.0, 4.0, 6.0]),
    )

    assert response == {"id": "uploaded_1"}
    assert messages == [
        "Video upload progress: 32% (speed: 16 MB/s)",
        "Video upload progress: 64% (speed: 16 MB/s)",
        "Video upload progress: 100% (speed: 18 MB/s)",
    ]


def test_format_file_size_uses_human_readable_units() -> None:
    assert format_file_size(100 * 1024 * 1024) == "100 MB"


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


def test_uploaded_history_matches_unicode_composition() -> None:
    filename = "2026-06-01 - Ёж и йога — ёлка Йога ānāpānasati ṭīkā.mp4"
    history = {
        f"english/{unicodedata.normalize('NFD', filename)}": {"status": "uploaded"}
    }

    assert is_uploaded_in_history(history, filename)
    assert is_uploaded_in_history(history, unicodedata.normalize("NFD", filename))


def test_uploaded_drive_key_matches_unicode_composition() -> None:
    filename = "2026-06-01 - Ёж и йога ānāpānasati.mp4"
    key = make_history_key(Path(filename), "Meditation")
    history = {unicodedata.normalize("NFD", key): {"status": "uploaded"}}

    assert is_uploaded_key_in_history(history, key)


def test_find_path_by_normalized_name_returns_existing_decomposed_file(
    tmp_path: Path,
) -> None:
    filename = "2026-06-01 - Ёж и ānāpānasati.mp4"
    decomposed = unicodedata.normalize("NFD", filename)
    existing = tmp_path / decomposed
    existing.write_bytes(b"video")

    found = find_path_by_normalized_name(tmp_path, filename)

    assert found.exists()
    assert unicodedata.normalize("NFC", found.name) == unicodedata.normalize(
        "NFC", existing.name
    )
