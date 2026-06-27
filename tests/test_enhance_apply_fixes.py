"""Tests for enhance_apply_fixes script."""

import json
from pathlib import Path

import pytest

import scripts.enhance_apply_fixes as eaf


def test_single_replacement_applied(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text("Hello world, hello everyone.", encoding="utf-8")

    fix_list = [
        {
            "file": str(f),
            "replacements": [{"old": "hello", "new": "goodbye"}],
        }
    ]

    applied, skipped = eaf.apply_fixes(fix_list)
    assert applied == 1
    assert skipped == 0
    assert f.read_text(encoding="utf-8") == "Hello world, goodbye everyone."


def test_multiple_replacements_in_one_file(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text("The cat sat on the mat.", encoding="utf-8")

    fix_list = [
        {
            "file": str(f),
            "replacements": [
                {"old": "cat", "new": "dog"},
                {"old": "mat", "new": "rug"},
            ],
        }
    ]

    applied, skipped = eaf.apply_fixes(fix_list)
    assert applied == 2
    assert f.read_text(encoding="utf-8") == "The dog sat on the rug."


def test_old_not_found(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text("Hello world.", encoding="utf-8")

    fix_list = [
        {
            "file": str(f),
            "replacements": [{"old": "nonexistent", "new": "replacement"}],
        }
    ]

    applied, skipped = eaf.apply_fixes(fix_list)
    assert applied == 0
    assert f.read_text(encoding="utf-8") == "Hello world."


def test_old_appears_three_times_skipped(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text("x x x", encoding="utf-8")

    fix_list = [
        {
            "file": str(f),
            "replacements": [{"old": "x", "new": "y"}],
        }
    ]

    applied, skipped = eaf.apply_fixes(fix_list)
    assert applied == 0
    assert f.read_text(encoding="utf-8") == "x x x"


def test_empty_replacements_noop(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text("Hello world.", encoding="utf-8")

    fix_list = [
        {
            "file": str(f),
            "replacements": [],
        }
    ]

    applied, skipped = eaf.apply_fixes(fix_list)
    assert applied == 0


def test_main_with_file_arg(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    f = tmp_path / "test.md"
    f.write_text("Hello world.", encoding="utf-8")

    fix_json = tmp_path / "fixes.json"
    fix_json.write_text(
        json.dumps([{"file": str(f), "replacements": [{"old": "Hello", "new": "Hi"}]}])
    )

    ret = eaf.main([str(fix_json)])
    assert ret == 0
    assert f.read_text(encoding="utf-8") == "Hi world."


def test_main_with_stdin(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = tmp_path / "test.md"
    f.write_text("Hello world.", encoding="utf-8")

    fix_data = json.dumps(
        [{"file": str(f), "replacements": [{"old": "Hello", "new": "Hi"}]}]
    )

    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(fix_data))

    ret = eaf.main(["--stdin"])
    assert ret == 0
    assert f.read_text(encoding="utf-8") == "Hi world."
