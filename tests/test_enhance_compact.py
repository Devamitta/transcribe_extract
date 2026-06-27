"""Test suite for deterministic enhance state file retention and rotation."""

import re
from pathlib import Path

import pytest

from scripts.enhance_compact import (
    HUB_KEEP_SESSIONS_PER_SKILL,
    HISTORY_KEEP_SECTIONS,
    ROUTING_KEEP,
    compact,
    count_history_sections,
    count_session_blocks,
)


@pytest.fixture
def temp_enhance_files(tmp_path: Path) -> dict[str, Path]:
    """Create minimal temp enhance state files for testing."""
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    hub_path = tmp_path / "enhance-state.md"
    archive_path = tmp_path / "enhance-session-archive.md"
    history_path = tmp_path / "enhance-improvements-history.md"

    # Create hub with 2 skills, each with 5 sessions (should keep 2, move 3)
    hub_content = (
        """# Enhance State Hub

## Maintenance
Retention rules applied by enhance_compact.py

## Carried Patterns
- Test pattern (evergreen)

## Routing Handoffs
"""
        + "\n".join(f"- Handoff {i}" for i in range(15))
        + """

## Active Backlog

## Session Ledger

### /enhance-semantic-fix

#### Session 1: 2026-06-15
- data: 1

#### Session 2: 2026-06-16
- data: 2

#### Session 3: 2026-06-17
- data: 3

#### Session 4: 2026-06-18
- data: 4

#### Session 5: 2026-06-19
- data: 5

### /enhance-prompt

#### Session 1: 2026-06-15
- data: 1

#### Session 2: 2026-06-16
- data: 2

#### Session 3: 2026-06-17
- data: 3

#### Session 4: 2026-06-18
- data: 4

#### Session 5: 2026-06-19
- data: 5
"""
    )
    hub_path.write_text(hub_content)

    # Create archive with empty skill sections
    archive_content = """# Enhance Session Archive

## /enhance-semantic-fix

## /enhance-prompt
"""
    archive_path.write_text(archive_content)

    # Create history with 25 sections (should keep 20, move 5)
    history_lines = ["# Enhance Improvements History\n"]
    for i in range(25):
        day = 15 + i
        history_lines.append(f"\n## 2026-06-{day:02d}\n")
        history_lines.append("- Test item\n")

    history_path.write_text("".join(history_lines))

    return {
        "hub": hub_path,
        "archive": archive_path,
        "history": history_path,
        "archive_dir": archive_dir,
    }


def test_conservation_session_blocks(temp_enhance_files: dict[str, Path]) -> None:
    """Verify that no session blocks are lost during rotation."""
    hub = temp_enhance_files["hub"]
    archive = temp_enhance_files["archive"]
    history = temp_enhance_files["history"]
    archive_dir = temp_enhance_files["archive_dir"]

    # Count before
    before_hub = count_session_blocks(hub)
    before_archive = count_session_blocks(archive)

    assert before_hub == 10  # 2 skills × 5 sessions
    assert before_archive == 0

    # Run compaction
    compact(hub, archive, history, archive_dir)

    # Count after
    after_hub = count_session_blocks(hub)
    after_archive = count_session_blocks(archive)
    after_cold = count_session_blocks(archive_dir / "enhance-sessions-cold.md")

    total_before = before_hub + before_archive
    total_after = after_hub + after_archive + after_cold

    assert total_before == total_after, (
        f"Session block count changed: {total_before} → {total_after}"
    )


def test_conservation_history_sections(temp_enhance_files: dict[str, Path]) -> None:
    """Verify that no history sections are lost during rotation."""
    hub = temp_enhance_files["hub"]
    archive = temp_enhance_files["archive"]
    history = temp_enhance_files["history"]
    archive_dir = temp_enhance_files["archive_dir"]

    # Count before
    before_history = count_history_sections(history)
    before_hub_history = count_history_sections(hub)

    assert before_history == 25

    # Run compaction
    compact(hub, archive, history, archive_dir)

    # Count after
    after_history = count_history_sections(history)
    after_cold = count_history_sections(archive_dir / "enhance-improvements-cold.md")
    after_hub_history = count_history_sections(hub)

    total_before = before_history + before_hub_history
    total_after = after_history + after_cold + after_hub_history

    assert total_before == total_after, (
        f"History section count changed: {total_before} → {total_after}"
    )


def test_hub_per_skill_cap(temp_enhance_files: dict[str, Path]) -> None:
    """Verify that hub keeps only HUB_KEEP_SESSIONS_PER_SKILL per skill."""
    hub = temp_enhance_files["hub"]
    archive = temp_enhance_files["archive"]
    history = temp_enhance_files["history"]
    archive_dir = temp_enhance_files["archive_dir"]

    # Run compaction
    compact(hub, archive, history, archive_dir)

    # Count sessions per skill in hub
    hub_content = hub.read_text()
    skills = ["/enhance-semantic-fix", "/enhance-prompt"]

    for skill in skills:
        # Find skill subsection
        skill_section = re.search(rf"### {skill}.*?(?=### |\Z)", hub_content, re.DOTALL)
        assert skill_section is not None

        sessions = re.findall(r"#### Session (\d+):", skill_section.group(0))
        session_nums = [int(s) for s in sessions]

        assert len(session_nums) <= HUB_KEEP_SESSIONS_PER_SKILL, (
            f"{skill} has {len(session_nums)} sessions, should be <= {HUB_KEEP_SESSIONS_PER_SKILL}"
        )

        # Should keep the highest-numbered ones (most recent)
        if len(session_nums) > 0:
            assert max(session_nums) >= 4, f"{skill} should keep higher session numbers"


def test_highest_session_numbers_kept(
    temp_enhance_files: dict[str, Path],
) -> None:
    """Verify that the highest session numbers are kept in the hub."""
    hub = temp_enhance_files["hub"]
    archive = temp_enhance_files["archive"]
    history = temp_enhance_files["history"]
    archive_dir = temp_enhance_files["archive_dir"]

    # Run compaction
    compact(hub, archive, history, archive_dir)

    # Check hub and verify per-skill retention
    hub_content = hub.read_text()
    skills = ["/enhance-semantic-fix", "/enhance-prompt"]

    for skill in skills:
        # Find skill subsection
        skill_section = re.search(rf"### {skill}.*?(?=### |\Z)", hub_content, re.DOTALL)
        if skill_section is None:
            # Skill may have no sessions, which is OK
            continue

        sessions = re.findall(r"#### Session (\d+):", skill_section.group(0))
        session_nums = [int(s) for s in sessions]

        # Each skill should have at most HUB_KEEP_SESSIONS_PER_SKILL sessions
        assert len(session_nums) <= HUB_KEEP_SESSIONS_PER_SKILL, (
            f"{skill} has {len(session_nums)} sessions, should be <= {HUB_KEEP_SESSIONS_PER_SKILL}"
        )

        # If any sessions remain, they should be the highest-numbered ones
        if len(session_nums) > 0:
            max_session = max(session_nums)
            assert max_session >= 4, (
                f"{skill} kept {session_nums}, should include higher numbers (4+)"
            )


def test_idempotency(temp_enhance_files: dict[str, Path]) -> None:
    """Verify that running compaction twice yields identical results."""
    hub = temp_enhance_files["hub"]
    archive = temp_enhance_files["archive"]
    history = temp_enhance_files["history"]
    archive_dir = temp_enhance_files["archive_dir"]

    # Run once
    compact(hub, archive, history, archive_dir)

    # Capture state
    hub_after_1 = hub.read_text()
    archive_after_1 = archive.read_text()
    history_after_1 = history.read_text()
    cold_sessions_after_1 = (
        (archive_dir / "enhance-sessions-cold.md").read_text()
        if (archive_dir / "enhance-sessions-cold.md").exists()
        else ""
    )
    cold_history_after_1 = (
        (archive_dir / "enhance-improvements-cold.md").read_text()
        if (archive_dir / "enhance-improvements-cold.md").exists()
        else ""
    )

    # Run again
    compact(hub, archive, history, archive_dir)

    # Capture state
    hub_after_2 = hub.read_text()
    archive_after_2 = archive.read_text()
    history_after_2 = history.read_text()
    cold_sessions_after_2 = (
        (archive_dir / "enhance-sessions-cold.md").read_text()
        if (archive_dir / "enhance-sessions-cold.md").exists()
        else ""
    )
    cold_history_after_2 = (
        (archive_dir / "enhance-improvements-cold.md").read_text()
        if (archive_dir / "enhance-improvements-cold.md").exists()
        else ""
    )

    # Should be identical
    assert hub_after_1 == hub_after_2, "Hub changed on second run"
    assert archive_after_1 == archive_after_2, "Archive changed on second run"
    assert history_after_1 == history_after_2, "History changed on second run"
    assert cold_sessions_after_1 == cold_sessions_after_2, (
        "Cold sessions changed on second run"
    )
    assert cold_history_after_1 == cold_history_after_2, (
        "Cold history changed on second run"
    )


def test_routing_handoffs_capped(temp_enhance_files: dict[str, Path]) -> None:
    """Verify that routing handoffs are capped at ROUTING_KEEP."""
    hub = temp_enhance_files["hub"]
    archive = temp_enhance_files["archive"]
    history = temp_enhance_files["history"]
    archive_dir = temp_enhance_files["archive_dir"]

    # Run compaction
    compact(hub, archive, history, archive_dir)

    # Count routing handoffs
    hub_content = hub.read_text()
    routing_match = re.search(
        r"## Routing Handoffs.*?(?=## |\Z)", hub_content, re.DOTALL
    )
    assert routing_match is not None

    handoffs = re.findall(r"^- ", routing_match.group(0), re.MULTILINE)
    assert len(handoffs) <= ROUTING_KEEP, (
        f"Routing handoffs: {len(handoffs)} > {ROUTING_KEEP}"
    )


def test_history_sections_capped(temp_enhance_files: dict[str, Path]) -> None:
    """Verify that history sections are capped at HISTORY_KEEP_SECTIONS."""
    hub = temp_enhance_files["hub"]
    archive = temp_enhance_files["archive"]
    history = temp_enhance_files["history"]
    archive_dir = temp_enhance_files["archive_dir"]

    # Run compaction
    compact(hub, archive, history, archive_dir)

    # Count sections in history
    after_history = count_history_sections(history)

    assert after_history <= HISTORY_KEEP_SECTIONS, (
        f"History sections: {after_history} > {HISTORY_KEEP_SECTIONS}"
    )


def test_dry_run_no_writes(temp_enhance_files: dict[str, Path]) -> None:
    """Verify that --dry-run does not modify any files."""
    hub = temp_enhance_files["hub"]
    archive = temp_enhance_files["archive"]
    history = temp_enhance_files["history"]
    archive_dir = temp_enhance_files["archive_dir"]

    # Capture state before
    hub_before = hub.read_text()
    archive_before = archive.read_text()
    history_before = history.read_text()

    # Run with dry_run=True
    compact(hub, archive, history, archive_dir, dry_run=True)

    # Verify no changes
    assert hub.read_text() == hub_before, "Hub was modified during dry-run"
    assert archive.read_text() == archive_before, "Archive was modified during dry-run"
    assert history.read_text() == history_before, "History was modified during dry-run"


@pytest.fixture
def temp_enhance_files_three_skills(tmp_path: Path) -> dict[str, Path]:
    """Create temp files with three skills: /enhance, /enhance-prompt, /enhance-semantic-fix.

    This tests the prefix-collision bug where /enhance is a prefix of the other two.
    Hub has 6 sessions of /enhance, 7 of /enhance-prompt, and 2 of /enhance-semantic-fix.
    After keeping 2/skill, we should have:
    - Hub: /enhance 5,6; /enhance-prompt 15,16; /enhance-semantic-fix 26,27
    - Archive: correct blocks under correct skill headings (no cross-contamination)
    """
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    hub_path = tmp_path / "enhance-state.md"
    archive_path = tmp_path / "enhance-session-archive.md"
    history_path = tmp_path / "enhance-improvements-history.md"

    # Create hub with 3 skills where /enhance is a prefix of the others
    hub_content = """# Enhance State Hub

## Maintenance
Retention rules applied by enhance_compact.py

## Carried Patterns
- Test pattern (evergreen)

## Routing Handoffs
- Handoff 1

## Active Backlog

## Session Ledger

### /enhance-semantic-fix

#### Session 26: 2026-06-26
- skill: enhance-semantic-fix
- session: 26

#### Session 27: 2026-06-27
- skill: enhance-semantic-fix
- session: 27

### /enhance

#### Session 1: 2026-06-01
- skill: enhance
- session: 1

#### Session 2: 2026-06-02
- skill: enhance
- session: 2

#### Session 3: 2026-06-03
- skill: enhance
- session: 3

#### Session 4: 2026-06-04
- skill: enhance
- session: 4

#### Session 5: 2026-06-05
- skill: enhance
- session: 5

#### Session 6: 2026-06-06
- skill: enhance
- session: 6

### /enhance-prompt

#### Session 10: 2026-06-10
- skill: enhance-prompt
- session: 10

#### Session 11: 2026-06-11
- skill: enhance-prompt
- session: 11

#### Session 12: 2026-06-12
- skill: enhance-prompt
- session: 12

#### Session 13: 2026-06-13
- skill: enhance-prompt
- session: 13

#### Session 14: 2026-06-14
- skill: enhance-prompt
- session: 14

#### Session 15: 2026-06-15
- skill: enhance-prompt
- session: 15

#### Session 16: 2026-06-16
- skill: enhance-prompt
- session: 16
"""
    hub_path.write_text(hub_content)

    # Create archive with empty skill sections (same order as hub for boundary-finding challenges)
    archive_content = """# Enhance Session Archive

## /enhance

## /enhance-prompt

## /enhance-semantic-fix
"""
    archive_path.write_text(archive_content)

    # Create minimal history file
    history_content = """# Enhance Improvements History

## 2026-06-01
- Test item
"""
    history_path.write_text(history_content)

    return {
        "hub": hub_path,
        "archive": archive_path,
        "history": history_path,
        "archive_dir": archive_dir,
    }


def test_three_skills_exact_matching(
    temp_enhance_files_three_skills: dict[str, Path],
) -> None:
    """Test that /enhance, /enhance-prompt, /enhance-semantic-fix are matched exactly.

    This regression test verifies the fix for the prefix-collision bug where
    '/enhance' is a prefix of '/enhance-prompt' and '/enhance-semantic-fix'.

    Before fix: hub /enhance-semantic-fix sessions were incorrectly appended under
    a duplicate or wrong archive heading because startswith() matching caused collision.

    After fix: exact matching ensures blocks land under correct skill headings.
    """
    hub = temp_enhance_files_three_skills["hub"]
    archive = temp_enhance_files_three_skills["archive"]
    history = temp_enhance_files_three_skills["history"]
    archive_dir = temp_enhance_files_three_skills["archive_dir"]

    # Run compaction (keep 2 sessions per skill)
    compact(hub, archive, history, archive_dir, hub_keep=2)

    # Read results
    hub_content = hub.read_text()
    archive_content = archive.read_text()

    # ===========================================
    # Assert 1: Hub keeps exactly the top 2 per skill
    # ===========================================
    skills = ["/enhance", "/enhance-prompt", "/enhance-semantic-fix"]
    expected_hub_keeps = {
        "/enhance": {5, 6},
        "/enhance-prompt": {15, 16},
        "/enhance-semantic-fix": {26, 27},
    }

    for skill in skills:
        # Find skill subsection in hub using exact regex
        skill_section = re.search(
            rf"### {re.escape(skill)}\s*\n(.*?)(?=^### |^## |\Z)",
            hub_content,
            re.MULTILINE | re.DOTALL,
        )
        assert skill_section is not None, f"Skill {skill} not found in hub"

        sessions = re.findall(r"#### Session (\d+):", skill_section.group(1))
        session_nums = set(int(s) for s in sessions)

        assert session_nums == expected_hub_keeps[skill], (
            f"{skill}: kept {session_nums}, expected {expected_hub_keeps[skill]}"
        )

    # ===========================================
    # Assert 2: Archive has exactly one heading per skill
    # ===========================================
    for skill in skills:
        # Count how many times the exact skill heading appears
        heading_pattern = f"^## {re.escape(skill)}$"
        headings = re.findall(heading_pattern, archive_content, re.MULTILINE)
        assert len(headings) == 1, (
            f"Archive has {len(headings)} heading(s) for {skill}, expected 1"
        )

    # ===========================================
    # Assert 3: No blocks bleed across skill boundaries
    # ===========================================
    # For each skill, verify that all sessions under it belong to that skill
    for skill in skills:
        skill_section = re.search(
            rf"## {re.escape(skill)}\s*\n(.*?)(?=^## |\Z)",
            archive_content,
            re.MULTILINE | re.DOTALL,
        )
        if skill_section is None:
            # Empty section is OK (no sessions moved for that skill)
            continue

        section_text = skill_section.group(1)
        # Extract all session blocks in this section
        session_entries = re.findall(r"- skill: (\S+)", section_text)

        # Each entry should belong to this skill (compare the extracted skill name)
        expected_skill_name = skill.lstrip("/")  # e.g., "/enhance" → "enhance"
        for entry_skill in session_entries:
            assert entry_skill == expected_skill_name, (
                f"Found '{entry_skill}' under '{skill}' archive section"
            )

    # ===========================================
    # Assert 4: Moved sessions in archive sum to correct totals
    # ===========================================
    expected_archive_sessions = {
        "/enhance": {1, 2, 3, 4},  # 6 total, keep 2, move 4
        "/enhance-prompt": {10, 11, 12, 13, 14},  # 7 total, keep 2, move 5
        "/enhance-semantic-fix": set(),  # 2 total, keep 2, move 0
    }

    for skill in skills:
        skill_section = re.search(
            rf"## {re.escape(skill)}\s*\n(.*?)(?=^## |\Z)",
            archive_content,
            re.MULTILINE | re.DOTALL,
        )
        if skill_section is None:
            archive_sessions = set()
        else:
            sessions = re.findall(r"#### Session (\d+):", skill_section.group(1))
            archive_sessions = set(int(s) for s in sessions)

        assert archive_sessions == expected_archive_sessions[skill], (
            f"{skill} archive has {archive_sessions}, expected {expected_archive_sessions[skill]}"
        )
