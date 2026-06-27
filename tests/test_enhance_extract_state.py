"""Tests for enhance_extract_state script."""

from pathlib import Path

import scripts.enhance_extract_state as ees

FIXTURE_TEXT = """# Enhance State Hub

## Carried Patterns
- [stage: extract] Headline Extraction Risk
- [stage: polish] Under-compression (open, 2026-06-15)
- [stage: extract] Nibbana risk (open, 2026-06-01)

## Routing Handoffs
- **2026-06-16 — /enhance → /enhance-prompt:** extract under-compression
- **2026-06-15 — /enhance → /enhance-semantic-fix:** teams/temples pattern
- **2026-06-14 — /enhance → /enhance-prompt:** polish readability

## Active Backlog
- Issue 1: over-compression in polish stage
- Issue 2: Pali terminology missing
- Issue 3: formatting inconsistency

## Session Ledger
### /enhance
#### Session 1: 2026-06-01
- last_run: 2026-06-01
"""


def test_stage_filtered_carried_patterns(tmp_path: Path) -> None:
    hub = tmp_path / "enhance-state.md"
    hub.write_text(FIXTURE_TEXT, encoding="utf-8")

    text = hub.read_text(encoding="utf-8")
    section = ees.extract_section(text, "Carried Patterns")
    filtered = ees.filter_by_stage(section, "extract")

    assert "Headline Extraction Risk" in filtered
    assert "Nibbana risk" in filtered
    assert "Under-compression" not in filtered


def test_all_carried_patterns_no_filter(tmp_path: Path) -> None:
    hub = tmp_path / "enhance-state.md"
    hub.write_text(FIXTURE_TEXT, encoding="utf-8")

    text = hub.read_text(encoding="utf-8")
    section = ees.extract_section(text, "Carried Patterns")

    assert "extract" in section
    assert "polish" in section


def test_routing_handoffs_extraction(tmp_path: Path) -> None:
    hub = tmp_path / "enhance-state.md"
    hub.write_text(FIXTURE_TEXT, encoding="utf-8")

    text = hub.read_text(encoding="utf-8")
    result = ees.extract_routing_handoffs(text)

    assert "enhance-prompt" in result
    assert "enhance-semantic-fix" in result
    assert len(result.split("\n")) == 3


def test_active_backlog_extraction(tmp_path: Path) -> None:
    hub = tmp_path / "enhance-state.md"
    hub.write_text(FIXTURE_TEXT, encoding="utf-8")

    text = hub.read_text(encoding="utf-8")
    result = ees.extract_active_backlog(text)

    assert "Issue 1" in result
    assert "Issue 3" in result


def test_missing_file_no_crash() -> None:
    section = ees.extract_section("", "Carried Patterns")
    assert section == ""

    result = ees.filter_by_stage("", "extract")
    assert result == ""

    result = ees.extract_routing_handoffs("")
    assert result == ""

    result = ees.extract_active_backlog("")
    assert result == ""


def test_section_not_found() -> None:
    text = "# Hub\n\n## Carried Patterns\n- item\n"
    section = ees.extract_section(text, "Active Backlog")
    assert section == ""


def test_main_extract_stage(tmp_path: Path, capsys) -> None:
    hub = tmp_path / "enhance-state.md"
    hub.write_text(FIXTURE_TEXT, encoding="utf-8")

    ret = ees.main(
        ["--section", "carried_patterns", "--stage", "extract", "--hub", str(hub)]
    )
    assert ret == 0

    captured = capsys.readouterr()
    assert "Headline Extraction Risk" in captured.out
    assert "Under-compression" not in captured.out


def test_main_routing_handoffs(tmp_path: Path, capsys) -> None:
    hub = tmp_path / "enhance-state.md"
    hub.write_text(FIXTURE_TEXT, encoding="utf-8")

    ret = ees.main(["--section", "routing_handoffs", "--hub", str(hub)])
    assert ret == 0

    captured = capsys.readouterr()
    assert "enhance-prompt" in captured.out


def test_main_active_backlog(tmp_path: Path, capsys) -> None:
    hub = tmp_path / "enhance-state.md"
    hub.write_text(FIXTURE_TEXT, encoding="utf-8")

    ret = ees.main(["--section", "active_backlog", "--hub", str(hub)])
    assert ret == 0

    captured = capsys.readouterr()
    assert "Issue 1" in captured.out


def test_main_hub_override(tmp_path: Path, capsys) -> None:
    hub = tmp_path / "custom-hub.md"
    hub.write_text(FIXTURE_TEXT, encoding="utf-8")

    ret = ees.main(["--section", "active_backlog", "--hub", str(hub)])
    assert ret == 0

    captured = capsys.readouterr()
    assert "Issue 1" in captured.out
