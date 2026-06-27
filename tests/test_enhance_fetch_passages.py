"""Tests for enhance_fetch_passages script."""

from pathlib import Path

import scripts.enhance_fetch_passages as efp


FIXTURE_TEXT = """line 1
line 2
line 3
line 4
line 5
line 6
line 7
line 8
line 9
line 10"""


def test_exact_line_range_fetch(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text(FIXTURE_TEXT, encoding="utf-8")

    result = efp.fetch_passage(f, 3, 5, context_lines=0)
    assert result is not None
    assert ">>> L3:" in result
    assert ">>> L5:" in result
    assert "L2:" not in result


def test_context_lines_included(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text(FIXTURE_TEXT, encoding="utf-8")

    result = efp.fetch_passage(f, 3, 5, context_lines=1)
    assert result is not None
    assert "L2:" in result
    assert ">>> L3:" in result
    assert "L6:" in result


def test_line_numbers_beyond_eof_clamped(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text(FIXTURE_TEXT, encoding="utf-8")

    result = efp.fetch_passage(f, 8, 20, context_lines=0)
    assert result is not None
    assert ">>> L8:" in result
    assert ">>> L10:" in result


def test_overlapping_ranges_merged() -> None:
    ranges: list[tuple[int, int]] = [(3, 6), (4, 8), (10, 12), (11, 14)]
    merged = efp.merge_ranges(ranges)
    assert merged == [(3, 8), (10, 14)]


def test_single_range_no_merge() -> None:
    ranges: list[tuple[int, int]] = [(5, 10)]
    merged = efp.merge_ranges(ranges)
    assert merged == [(5, 10)]


def test_adjacent_ranges_merged() -> None:
    ranges: list[tuple[int, int]] = [(1, 3), (4, 6)]
    merged = efp.merge_ranges(ranges)
    assert merged == [(1, 6)]


def test_file_not_found() -> None:
    result = efp.fetch_passage(Path("nonexistent.md"), 1, 10)
    assert result is None


def test_single_line_range(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text(FIXTURE_TEXT, encoding="utf-8")

    result = efp.fetch_passage(f, 5, 5, context_lines=0)
    assert result is not None
    assert ">>> L5:" in result
    assert "L6:" not in result
