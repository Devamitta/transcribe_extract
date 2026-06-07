"""Tests current-run source scoping helpers."""

from pathlib import Path

from tools.source_scope import (
    path_matches_filter,
    read_source_filter,
    source_matches_filter,
)


def test_source_filter_matches_full_path_name_and_stem(tmp_path: Path) -> None:
    source_log = tmp_path / "sources.log"
    source_log.write_text(
        str(tmp_path / "output" / "video" / "english" / "Talk Name.mp4") + "\n",
        encoding="utf-8",
    )

    source_filter = read_source_filter(source_log)

    assert source_matches_filter(
        str(tmp_path / "output" / "video" / "english" / "Talk Name.mp4"),
        source_filter,
    )
    assert source_matches_filter("Talk Name.mp4", source_filter)
    assert source_matches_filter("Talk Name", source_filter)
    assert not source_matches_filter("Backlog Talk.mp4", source_filter)
    assert path_matches_filter(
        tmp_path / "output" / "video" / "english" / "Talk Name.mp4",
        source_filter,
    )
    assert not path_matches_filter(tmp_path / "other" / "Talk Name.mp4", source_filter)


def test_empty_source_filter_matches_nothing(tmp_path: Path) -> None:
    source_log = tmp_path / "sources.log"
    source_log.write_text("", encoding="utf-8")

    assert not source_matches_filter("Talk Name.mp4", read_source_filter(source_log))
