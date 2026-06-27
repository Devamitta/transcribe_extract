"""Tests for enhance_queue semantic-report queue script."""

import json
import time
import unicodedata
from pathlib import Path

import pytest

import scripts.enhance_queue as eq


def _nfd_from_nfc(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def test_nfc_normalization_matching(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    sem_dir = repo / "reports" / "semantic" / "interview"
    sem_dir.mkdir(parents=True)

    nfc_name = "r\u0101port.md"
    nfd_name = _nfd_from_nfc(nfc_name)

    (sem_dir / nfd_name).write_text("")
    time.sleep(0.01)

    data_dir = repo / "kamma" / "enhance" / "data"
    data_dir.mkdir(parents=True)
    ledger_path = data_dir / "semantic-ledger.json"
    ledger_path.write_text(
        json.dumps({"processed_files": [{"file": nfc_name, "mtime": 0}]})
    )

    ledger_mtimes = eq.load_ledger_mtimes(ledger_path)
    report_list, total = eq.build_report_list(sem_dir, ledger_mtimes)

    assert total == 1
    assert len(report_list) == 1


def test_mtime_comparison_newer_not_reviewed(tmp_path: Path) -> None:
    sem_dir = tmp_path / "semantic"
    sem_dir.mkdir(parents=True)

    r_path = sem_dir / "report.md"
    r_path.write_text("")
    r_mtime = r_path.stat().st_mtime

    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(
        json.dumps({"processed_files": [{"file": "report.md", "mtime": r_mtime - 10}]})
    )

    ledger_mtimes = eq.load_ledger_mtimes(ledger_path)
    unreviewed, total = eq.build_report_list(sem_dir, ledger_mtimes)

    assert total == 1
    assert len(unreviewed) == 1


def test_mtime_comparison_older_is_reviewed(tmp_path: Path) -> None:
    sem_dir = tmp_path / "semantic"
    sem_dir.mkdir(parents=True)

    r_path = sem_dir / "report.md"
    r_path.write_text("")
    r_mtime = r_path.stat().st_mtime

    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(
        json.dumps(
            {"processed_files": [{"file": "report.md", "mtime": r_mtime + 3600}]}
        )
    )

    ledger_mtimes = eq.load_ledger_mtimes(ledger_path)
    unreviewed, total = eq.build_report_list(sem_dir, ledger_mtimes)

    assert total == 1
    assert len(unreviewed) == 0


def test_limit_enforcement(tmp_path: Path) -> None:
    sem_dir = tmp_path / "semantic"
    sem_dir.mkdir(parents=True)

    for i in range(15):
        (sem_dir / f"report_{i:02d}.md").write_text("")

    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps({"processed_files": []}))

    ledger_mtimes = eq.load_ledger_mtimes(ledger_path)
    unreviewed, total = eq.build_report_list(sem_dir, ledger_mtimes)

    limited = unreviewed[: eq.SESSION_LIMIT]
    pending = max(0, len(unreviewed) - eq.SESSION_LIMIT)

    assert total == 15
    assert len(limited) == 10
    assert pending == 5


def test_empty_ledger_all_unreviewed(tmp_path: Path) -> None:
    sem_dir = tmp_path / "semantic"
    sem_dir.mkdir(parents=True)

    (sem_dir / "r1.md").write_text("")
    (sem_dir / "r2.md").write_text("")

    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps({"processed_files": []}))

    ledger_mtimes = eq.load_ledger_mtimes(ledger_path)
    unreviewed, total = eq.build_report_list(sem_dir, ledger_mtimes)

    assert total == 2
    assert len(unreviewed) == 2


def test_missing_ledger_all_unreviewed(tmp_path: Path) -> None:
    sem_dir = tmp_path / "semantic"
    sem_dir.mkdir(parents=True)

    (sem_dir / "r1.md").write_text("")

    ledger_path = tmp_path / "nonexistent.json"
    ledger_mtimes = eq.load_ledger_mtimes(ledger_path)
    unreviewed, total = eq.build_report_list(sem_dir, ledger_mtimes)

    assert total == 1
    assert len(unreviewed) == 1


def test_main_output(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    sem_dir = tmp_path / "reports" / "semantic" / "interview"
    sem_dir.mkdir(parents=True)

    (sem_dir / "r1.md").write_text("")

    data_dir = tmp_path / "kamma" / "enhance" / "data"
    data_dir.mkdir(parents=True)
    ledger_path = data_dir / "semantic-ledger.json"
    ledger_path.write_text(json.dumps({"processed_files": []}))

    _ = eq.main(["--root", str(tmp_path), "--folder", "interview"])

    captured = capsys.readouterr()
    output = captured.out
    assert "Total on disk" in output
    assert '"pending_count"' in output
    json_start = output.index("\n{")
    json_end = output.rfind("}") + 1
    result = json.loads(output[json_start + 1 : json_end])
    assert len(result["reports"]) == 1
    assert result["pending_count"] == 0
