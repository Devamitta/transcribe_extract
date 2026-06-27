"""Tests for enhance_detect state detection script."""

import json
from pathlib import Path

import pytest

import scripts.enhance_detect as ed

FIXTURE_CARRIED = """### Carried Patterns
- [stage: extract] nibbāna (open, 2026-06-01)
- [stage: polish] under-compression (open, 2026-06-15)
- [stage: pali, semantic] asubha issue (open, 2026-06-10)
- [stage: extract] no lifecycle marker pattern
"""


def test_count_files_empty(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert ed.count_files(empty_dir) == 0


def test_count_files_with_md(tmp_path: Path) -> None:
    d = tmp_path / "files"
    d.mkdir()
    (d / "a.md").write_text("")
    (d / "b.md").write_text("")
    (d / "other.txt").write_text("")
    assert ed.count_files(d) == 2


def test_count_files_missing_dir(tmp_path: Path) -> None:
    assert ed.count_files(tmp_path / "nonexistent") == 0


def test_compute_unreviewed_all_new(tmp_path: Path) -> None:
    sem_dir = tmp_path / "semantic"
    sem_dir.mkdir()
    (sem_dir / "r1.md").write_text("")
    (sem_dir / "r2.md").write_text("")

    ledger_path = tmp_path / "ledger.json"
    assert ed.compute_unreviewed(sem_dir, ledger_path) == 2


def test_compute_unreviewed_with_ledger(tmp_path: Path) -> None:
    sem_dir = tmp_path / "semantic"
    sem_dir.mkdir()
    (sem_dir / "r1.md").write_text("")
    (sem_dir / "r2.md").write_text("")

    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(
        json.dumps({"processed_files": [{"file": "r1.md"}, {"file": "r2.md"}]})
    )
    assert ed.compute_unreviewed(sem_dir, ledger_path) == 0


def test_compute_unreviewed_partial(tmp_path: Path) -> None:
    sem_dir = tmp_path / "semantic"
    sem_dir.mkdir()
    (sem_dir / "r1.md").write_text("")
    (sem_dir / "r2.md").write_text("")

    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps({"processed_files": [{"file": "r1.md"}]}))
    assert ed.compute_unreviewed(sem_dir, ledger_path) == 1


def test_parse_open_patterns(tmp_path: Path) -> None:
    hub = tmp_path / "enhance-state.md"
    hub.write_text(FIXTURE_CARRIED, encoding="utf-8")

    patterns = ed.parse_open_patterns(hub)
    assert len(patterns) == 3

    stages_seen = {str(p["stage"]) for p in patterns if "stage" in p}
    assert "extract" in stages_seen
    assert "polish" in stages_seen
    assert "pali" in stages_seen


def test_parse_open_patterns_no_hub() -> None:
    patterns = ed.parse_open_patterns(Path("nonexistent.md"))
    assert len(patterns) == 0


def test_parse_open_patterns_no_open_entries(tmp_path: Path) -> None:
    hub = tmp_path / "hub.md"
    hub.write_text(
        "### Carried Patterns\n- [stage: extract] no-date pattern (no lifecycle)\n",
        encoding="utf-8",
    )
    patterns = ed.parse_open_patterns(hub)
    assert len(patterns) == 0


def test_main_json_output(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    corrected_dir = tmp_path / "output" / "corrected_pali" / "interview"
    corrected_dir.mkdir(parents=True)
    (corrected_dir / "a.md").write_text("")
    (corrected_dir / "b.md").write_text("")

    extracted_dir = tmp_path / "output" / "extracted" / "interview"
    extracted_dir.mkdir(parents=True)
    (extracted_dir / "a.md").write_text("")

    polished_dir = tmp_path / "output" / "polished" / "interview"
    polished_dir.mkdir(parents=True)

    sem_dir = tmp_path / "reports" / "semantic" / "interview"
    sem_dir.mkdir(parents=True)
    (sem_dir / "r1.md").write_text("")

    hub_dir = tmp_path / "kamma" / "enhance"
    hub_dir.mkdir(parents=True)
    hub = hub_dir / "enhance-state.md"
    hub.write_text("### Carried Patterns\n", encoding="utf-8")

    data_dir = tmp_path / "kamma" / "enhance" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "semantic-ledger.json").write_text("{}")

    _ = ed.main(["--root", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["corrected_count"] == 2
    assert result["extracted_count"] == 1
    assert result["polished_count"] == 0
    assert result["unreviewed_semantic"] == 1
    assert result["open_patterns"] == []


def test_main_with_open_patterns(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    corrected_dir = tmp_path / "output" / "corrected_pali" / "interview"
    corrected_dir.mkdir(parents=True)

    extracted_dir = tmp_path / "output" / "extracted" / "interview"
    extracted_dir.mkdir(parents=True)

    polished_dir = tmp_path / "output" / "polished" / "interview"
    polished_dir.mkdir(parents=True)

    sem_dir = tmp_path / "reports" / "semantic" / "interview"
    sem_dir.mkdir(parents=True)

    hub_dir = tmp_path / "kamma" / "enhance"
    hub_dir.mkdir(parents=True)
    hub = hub_dir / "enhance-state.md"
    hub.write_text(FIXTURE_CARRIED, encoding="utf-8")

    data_dir = tmp_path / "kamma" / "enhance" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "semantic-ledger.json").write_text("{}")

    _ = ed.main(["--root", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert len(result["open_patterns"]) == 3
    assert result["corrected_count"] == 0
