"""Regression tests for deterministic privacy scanning and reporting."""

import unicodedata
from pathlib import Path

import pytest

from scripts import check_privacy
from tools.privacy import apply_fixes, scan_text


def test_scan_text_detects_nfc_and_nfd_names_and_places() -> None:
    nfd_teacher = unicodedata.normalize("NFD", "Bhikkhu Anālayo")
    text = f"Kittisobhana and {nfd_teacher} spoke at Sasanarakkha."

    hits = scan_text(text)

    assert {hit.term for hit in hits} == {
        "Kittisobhana",
        "Bhikkhu Anālayo",
        "Sasanarakkha",
    }
    assert all(hit.context for hit in hits)


def test_scan_text_passes_clean_dhamma_text() -> None:
    hits = scan_text("A teacher explained impermanence at a monastery.")

    assert hits == []


def test_apply_fixes_replaces_and_reports() -> None:
    fixed, fixes = apply_fixes("Kittisobhana spoke at Sasanarakkha.")

    assert fixed == "a teacher spoke at a monastery."
    assert {(fix.term, fix.replacement, fix.count) for fix in fixes} == {
        ("Kittisobhana", "a teacher", 1),
        ("Sasanarakkha", "a monastery", 1),
    }


def test_check_privacy_report_and_fix_mode_with_fallback_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    polished_file = tmp_path / "output" / "polished" / "interview" / "talk.md"
    extracted_shadow = tmp_path / "output" / "extracted" / "interview" / "talk.md"
    extracted_only = tmp_path / "output" / "extracted" / "only.md"
    polished_file.parent.mkdir(parents=True)
    extracted_shadow.parent.mkdir(parents=True)
    extracted_only.parent.mkdir(parents=True, exist_ok=True)
    polished_file.write_text("Kittisobhana taught at Sasanarakkha.", encoding="utf-8")
    extracted_shadow.write_text("This should not be scanned.", encoding="utf-8")
    extracted_only.write_text("Bhikkhu Anālayo mentioned Amaravati.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = check_privacy.main(["--fix"])
    report_files = list((tmp_path / "reports" / "privacy").glob("privacy_*.md"))

    assert exit_code == 0
    assert polished_file.read_text(encoding="utf-8") == (
        "a teacher taught at a monastery."
    )
    assert extracted_only.read_text(encoding="utf-8") == (
        "Bhikkhu Anālayo mentioned Amaravati."
    )
    assert len(report_files) == 1
    report = report_files[0].read_text(encoding="utf-8")
    assert "interview/talk.md" in report
    assert "only.md" in report
    assert "Kittisobhana" in report
    assert "Sasanarakkha" in report
    assert "Bhikkhu Anālayo" in report
    assert "Amaravati" in report
    assert "Fix skipped" in report
