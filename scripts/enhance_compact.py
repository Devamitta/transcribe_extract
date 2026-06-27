"""Deterministic retention/rotation tool for enhance state files with no LLM involvement."""

import re
import tempfile
from pathlib import Path
from typing import NamedTuple
from sys import exit

from tools.printer import printer as pr


# Constants for retention policy
HUB_KEEP_SESSIONS_PER_SKILL = 2
ARCHIVE_KEEP_SESSIONS_PER_SKILL = 12
HISTORY_KEEP_SECTIONS = 20
ROUTING_KEEP = 10


class SessionBlock(NamedTuple):
    """A parsed session block with heading and content lines."""

    session_num: int
    heading_line: str
    content_lines: list[str]


def resolve_repo_root() -> Path:
    """Resolve the repo root from the script location."""
    return Path(__file__).resolve().parents[1]


def parse_session_blocks(
    lines: list[str], skill_section_start: int, skill_section_end: int
) -> list[SessionBlock]:
    """
    Parse session blocks within a skill subsection.

    A session block starts with #### Session N: and continues until the next
    #### , ### , ## , or EOF.
    """
    blocks: list[SessionBlock] = []
    i = skill_section_start

    while i < skill_section_end:
        line = lines[i]

        # Check if this is a session heading
        if line.startswith("#### Session "):
            heading_line = line
            # Extract session number
            match = re.match(r"#### Session (\d+):", line)
            if match:
                session_num = int(match.group(1))
                # Collect content until next #### , ### , ## , or EOF
                content_lines: list[str] = []
                i += 1

                while i < skill_section_end:
                    if (
                        lines[i].startswith("#### ")
                        or lines[i].startswith("### ")
                        or lines[i].startswith("## ")
                    ):
                        break
                    content_lines.append(lines[i])
                    i += 1

                blocks.append(SessionBlock(session_num, heading_line, content_lines))
                continue

        i += 1

    return blocks


def find_skill_subsection(
    lines: list[str], skill_name: str, start_from: int = 0
) -> tuple[int, int] | None:
    """
    Find a ### <skill_name> subsection.
    Returns (start_idx, end_idx) or None if not found.
    """
    for i in range(start_from, len(lines)):
        # Extract skill name from heading line (exact match, not prefix)
        if lines[i].startswith("### "):
            line_skill = lines[i][4:].strip()  # Remove "### " and whitespace
            if line_skill == skill_name:
                # Find where this section ends (next ### , ## , or EOF)
                end_idx = len(lines)
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith("### ") or lines[j].startswith("## "):
                        end_idx = j
                        break
                return (i, end_idx)

    return None


def find_skill_heading_in_archive(lines: list[str], skill_name: str) -> int | None:
    """Find a ## <skill_name> heading in an archive file. Returns line index or None."""
    for i, line in enumerate(lines):
        # Extract skill name from heading line (exact match, not prefix)
        if line.startswith("## "):
            line_skill = line[3:].strip()  # Remove "## " and whitespace
            if line_skill == skill_name:
                return i
    return None


def rotate_hub_to_archive(
    hub_path: Path,
    archive_path: Path,
    keep_per_skill: int = HUB_KEEP_SESSIONS_PER_SKILL,
) -> dict[str, int]:
    """
    Move old session blocks from hub to archive.

    Returns a dict of {skill: num_blocks_moved}.
    """
    hub_lines = hub_path.read_text().splitlines(keepends=True)
    archive_lines = archive_path.read_text().splitlines(keepends=True)

    # Find Session Ledger section in hub
    ledger_start = None
    ledger_end = len(hub_lines)
    for i, line in enumerate(hub_lines):
        if line.startswith("## Session Ledger"):
            ledger_start = i
        elif ledger_start is not None and line.startswith("## "):
            ledger_end = i
            break

    if ledger_start is None:
        return {}

    moved_counts: dict[str, int] = {}

    # Process each skill subsection in the ledger
    search_from = ledger_start + 1
    while True:
        # Find next ### skill heading
        skill_start: int | None = None
        skill_name: str | None = None
        for i in range(search_from, ledger_end):
            if hub_lines[i].startswith("### "):
                skill_match = re.match(r"### (/\S+)", hub_lines[i])
                if skill_match:
                    skill_name = skill_match.group(1)
                    skill_start = i
                    break

        if skill_start is None:
            break

        # Find skill section end
        skill_end = ledger_end
        for i in range(skill_start + 1, ledger_end):
            if hub_lines[i].startswith("### ") or hub_lines[i].startswith("## "):
                skill_end = i
                break

        # Parse session blocks for this skill
        blocks = parse_session_blocks(hub_lines, skill_start + 1, skill_end)

        if len(blocks) > keep_per_skill:
            # Sort by session number, keep the highest ones
            blocks.sort(key=lambda b: b.session_num)
            to_move = blocks[:-keep_per_skill]
            to_keep = blocks[-keep_per_skill:]

            # Reconstruct the skill section with only kept blocks
            new_section_lines = [hub_lines[skill_start]]  # skill heading
            for block in to_keep:
                new_section_lines.append(block.heading_line)
                new_section_lines.extend(block.content_lines)

            # Replace in hub
            hub_lines[skill_start:skill_end] = new_section_lines

            # Append moved blocks to archive
            if skill_name is not None:
                archive_skill_heading_idx = find_skill_heading_in_archive(
                    archive_lines, skill_name
                )
                if archive_skill_heading_idx is None:
                    # Create the heading at end of file
                    if archive_lines and not archive_lines[-1].endswith("\n"):
                        archive_lines[-1] += "\n"
                    archive_lines.append(f"\n## {skill_name}\n")
                    archive_skill_heading_idx = len(archive_lines) - 1

                # Find the end of this skill section in archive
                archive_skill_end = len(archive_lines)
                for i in range(archive_skill_heading_idx + 1, len(archive_lines)):
                    if archive_lines[i].startswith("## "):
                        archive_skill_end = i
                        break

                # Insert moved blocks at end of skill section (before next ## or EOF)
                blocks_to_append = []
                for block in to_move:
                    blocks_to_append.append(block.heading_line)
                    blocks_to_append.extend(block.content_lines)

                archive_lines[archive_skill_end:archive_skill_end] = blocks_to_append

                moved_counts[skill_name] = len(to_move)

            # After modification, search_from should be at the end of the new section
            search_from = skill_start + len(new_section_lines)
            # Recalculate ledger_end after modifying hub_lines
            ledger_end = len(hub_lines)
        else:
            # No modification; advance to the next skill heading (which sits at
            # skill_end). Using skill_end+1 here would skip that heading and
            # leave a later skill uncompacted.
            search_from = skill_end

    # Write back
    hub_path.write_text("".join(hub_lines))
    archive_path.write_text("".join(archive_lines))

    return moved_counts


def rotate_archive_to_cold(
    archive_path: Path,
    cold_path: Path,
    keep_per_skill: int = ARCHIVE_KEEP_SESSIONS_PER_SKILL,
) -> dict[str, int]:
    """
    Move old session blocks from archive to cold storage.

    Returns a dict of {skill: num_blocks_moved}.
    """
    archive_lines = archive_path.read_text().splitlines(keepends=True)
    cold_lines = (
        cold_path.read_text().splitlines(keepends=True) if cold_path.exists() else []
    )

    moved_counts: dict[str, int] = {}

    # Process each ## skill section in archive
    i = 0
    while i < len(archive_lines):
        line = archive_lines[i]

        if line.startswith("## ") and not line.startswith("## Session Ledger"):
            skill_match = re.match(r"## (/\S+)", line)
            if skill_match:
                skill_name: str = skill_match.group(1)
                skill_start = i
                skill_end = len(archive_lines)

                # Find end of section
                for j in range(i + 1, len(archive_lines)):
                    if archive_lines[j].startswith("## "):
                        skill_end = j
                        break

                # Parse blocks in this section
                blocks = parse_session_blocks(archive_lines, skill_start + 1, skill_end)

                if len(blocks) > keep_per_skill:
                    blocks.sort(key=lambda b: b.session_num)
                    to_move = blocks[:-keep_per_skill]
                    to_keep = blocks[-keep_per_skill:]

                    # Reconstruct section with kept blocks
                    new_section_lines = [archive_lines[skill_start]]
                    for block in to_keep:
                        new_section_lines.append(block.heading_line)
                        new_section_lines.extend(block.content_lines)

                    archive_lines[skill_start:skill_end] = new_section_lines

                    # Append to cold storage
                    cold_skill_heading_idx = find_skill_heading_in_archive(
                        cold_lines, skill_name
                    )
                    if cold_skill_heading_idx is None:
                        if cold_lines and not cold_lines[-1].endswith("\n"):
                            cold_lines[-1] += "\n"
                        cold_lines.append(f"\n## {skill_name}\n")
                        cold_skill_heading_idx = len(cold_lines) - 1

                    # Find end of skill section in cold
                    cold_skill_end = len(cold_lines)
                    for j in range(cold_skill_heading_idx + 1, len(cold_lines)):
                        if cold_lines[j].startswith("## "):
                            cold_skill_end = j
                            break

                    # Insert moved blocks
                    blocks_to_append = []
                    for block in to_move:
                        blocks_to_append.append(block.heading_line)
                        blocks_to_append.extend(block.content_lines)

                    cold_lines[cold_skill_end:cold_skill_end] = blocks_to_append

                    moved_counts[skill_name] = len(to_move)
                    i = skill_end
                    continue

        i += 1

    archive_path.write_text("".join(archive_lines))
    cold_path.write_text("".join(cold_lines))

    return moved_counts


def rotate_history_to_cold(
    history_path: Path,
    cold_path: Path,
    keep_sections: int = HISTORY_KEEP_SECTIONS,
) -> int:
    """
    Move old history sections to cold storage.

    Returns the number of sections moved.
    """
    history_lines = history_path.read_text().splitlines(keepends=True)
    cold_lines = (
        cold_path.read_text().splitlines(keepends=True) if cold_path.exists() else []
    )

    # Find all ## sections (chronological top-level sections)
    section_starts: list[int] = []
    for i, line in enumerate(history_lines):
        if re.match(r"^## \d{4}-\d{2}-\d{2}", line) or line.startswith(
            "## Resolved Patterns"
        ):
            section_starts.append(i)

    # Build sections with end indices
    sections: list[tuple[int, int]] = []
    for j in range(len(section_starts)):
        start = section_starts[j]
        end = (
            section_starts[j + 1] if j + 1 < len(section_starts) else len(history_lines)
        )
        sections.append((start, end))

    if len(sections) <= keep_sections:
        return 0

    # Keep the last keep_sections, move the rest
    to_move = sections[:-keep_sections]
    to_keep = sections[-keep_sections:]

    # Reconstruct history with kept sections
    new_history_lines: list[str] = []
    for start, end in to_keep:
        new_history_lines.extend(history_lines[start:end])

    # Append moved sections to cold
    for start, end in to_move:
        cold_lines.extend(history_lines[start:end])

    history_path.write_text("".join(new_history_lines))
    cold_path.write_text("".join(cold_lines))

    return len(to_move)


def move_resolved_patterns(
    hub_path: Path,
    history_path: Path,
    today: str = "2026-06-22",
) -> int:
    """
    Move resolved patterns from hub to history.

    Returns the number of patterns moved.
    """
    hub_lines = hub_path.read_text().splitlines(keepends=True)
    history_lines = history_path.read_text().splitlines(keepends=True)

    # Find Carried Patterns section
    patterns_start = None
    patterns_end = len(hub_lines)
    for i, line in enumerate(hub_lines):
        if line.startswith("## Carried Patterns"):
            patterns_start = i
        elif patterns_start is not None and line.startswith("## "):
            patterns_end = i
            break

    if patterns_start is None:
        return 0

    # Find patterns marked (resolved, YYYY-MM-DD)
    resolved_bullets: list[tuple[int, int]] = []
    i = patterns_start + 1

    while i < patterns_end:
        line = hub_lines[i]

        if line.startswith("- ") and "(resolved," in line:
            # Find the end of this bullet
            bullet_start = i
            i += 1
            while i < patterns_end:
                next_line = hub_lines[i]
                # Bullet ends at next - at col 0, or next ## , or EOF
                if next_line.startswith("- ") or next_line.startswith("## "):
                    break
                if (
                    not next_line.startswith("  ")
                    and next_line.strip()
                    and not next_line.startswith("-")
                ):
                    # Non-indented non-empty line that's not a bullet
                    break
                i += 1

            resolved_bullets.append((bullet_start, i))
        else:
            i += 1

    if not resolved_bullets:
        return 0

    # Collect resolved bullet text
    resolved_text: list[str] = []
    for start, end in resolved_bullets:
        resolved_text.extend(hub_lines[start:end])

    # Remove from hub (in reverse order to preserve indices)
    for start, end in reversed(resolved_bullets):
        del hub_lines[start:end]

    # Append to history under dated heading
    if history_lines and not history_lines[-1].endswith("\n"):
        history_lines[-1] += "\n"

    history_lines.append(f"\n### Resolved Patterns — {today}\n")
    history_lines.extend(resolved_text)

    hub_path.write_text("".join(hub_lines))
    history_path.write_text("".join(history_lines))

    return len(resolved_bullets)


def move_old_routing_handoffs(
    hub_path: Path,
    keep: int = ROUTING_KEEP,
) -> int:
    """
    Drop old routing handoffs (keep only the first keep entries).

    Returns the number of entries dropped.
    """
    lines = hub_path.read_text().splitlines(keepends=True)

    # Find Routing Handoffs section
    routing_start = None
    routing_end = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("## Routing Handoffs"):
            routing_start = i
        elif routing_start is not None and line.startswith("## "):
            routing_end = i
            break

    if routing_start is None:
        return 0

    # Collect top-level - bullets in order
    bullets: list[tuple[int, int]] = []
    i = routing_start + 1

    while i < routing_end:
        line = lines[i]

        if line.startswith("- "):
            bullet_start = i
            i += 1
            while i < routing_end:
                next_line = lines[i]
                # Bullet ends at next - at col 0, next ##, or blank+heading
                if next_line.startswith("- ") or next_line.startswith("## "):
                    break
                if not next_line.startswith("  ") and next_line.strip() == "":
                    # Check if followed by heading
                    if i + 1 < routing_end and lines[i + 1].startswith("## "):
                        i += 1
                        break
                i += 1

            bullets.append((bullet_start, i))
        else:
            i += 1

    if len(bullets) <= keep:
        return 0

    # Drop the oldest ones (keep only the first keep)
    to_drop = bullets[keep:]
    num_dropped = len(to_drop)

    # Remove in reverse order
    for start, end in reversed(to_drop):
        del lines[start:end]

    hub_path.write_text("".join(lines))

    return num_dropped


def count_session_blocks(path: Path) -> int:
    """Count all #### Session blocks in a file."""
    if not path.exists():
        return 0
    content = path.read_text()
    return len(re.findall(r"^#### Session \d+:", content, re.MULTILINE))


def count_history_sections(path: Path) -> int:
    """Count all ## YYYY-MM-DD history sections in a file."""
    if not path.exists():
        return 0
    content = path.read_text()
    return len(
        re.findall(
            r"^## (?:\d{4}-\d{2}-\d{2}|Resolved Patterns)", content, re.MULTILINE
        )
    )


def conservation_check(
    before_session_count: dict[str, int],
    after_session_count: dict[str, int],
    before_history_count: int,
    after_history_count: int,
) -> bool:
    """
    Verify that no data was lost during rotation.

    Returns True if check passes.
    """
    before_total = sum(before_session_count.values())
    after_total = sum(after_session_count.values())

    session_ok = before_total == after_total
    history_ok = before_history_count == after_history_count

    return session_ok and history_ok


def compact(
    hub_path: Path,
    archive_path: Path,
    history_path: Path,
    cold_base_path: Path,
    dry_run: bool = False,
    hub_keep: int = HUB_KEEP_SESSIONS_PER_SKILL,
    archive_keep: int = ARCHIVE_KEEP_SESSIONS_PER_SKILL,
    history_keep: int = HISTORY_KEEP_SECTIONS,
    routing_keep: int = ROUTING_KEEP,
) -> None:
    """
    Run the full compaction pipeline.
    """
    # Ensure cold archive directory exists
    cold_base_path.mkdir(parents=True, exist_ok=True)

    # Determine cold file paths
    sessions_cold_path = cold_base_path / "enhance-sessions-cold.md"
    improvements_cold_path = cold_base_path / "enhance-improvements-cold.md"

    # Create empty cold files if they don't exist
    if not sessions_cold_path.exists():
        sessions_cold_path.write_text("")
    if not improvements_cold_path.exists():
        improvements_cold_path.write_text("")

    # Count before
    before_hub_sessions = count_session_blocks(hub_path)
    before_archive_sessions = count_session_blocks(archive_path)
    before_cold_sessions = count_session_blocks(sessions_cold_path)
    before_total_sessions = (
        before_hub_sessions + before_archive_sessions + before_cold_sessions
    )

    before_hub_history = count_history_sections(hub_path)
    before_history_history = count_history_sections(history_path)
    before_cold_history = count_history_sections(improvements_cold_path)
    before_total_history = (
        before_hub_history + before_history_history + before_cold_history
    )

    before_session_count = {
        "hub": before_hub_sessions,
        "archive": before_archive_sessions,
        "cold": before_cold_sessions,
    }
    before_history_count = before_total_history

    pr.bip()

    if dry_run:
        # Run the real pipeline on throwaway copies so the preview matches the
        # real run exactly (including the archive→cold cascade) — no separate,
        # drift-prone re-implementation of the rotation logic.
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            run_hub = tdp / "hub.md"
            run_hub.write_text(hub_path.read_text())
            run_archive = tdp / "archive.md"
            run_archive.write_text(archive_path.read_text())
            run_history = tdp / "history.md"
            run_history.write_text(history_path.read_text())
            run_cold = tdp / "archive"
            run_cold.mkdir()
            run_sessions_cold = run_cold / "enhance-sessions-cold.md"
            run_sessions_cold.write_text(sessions_cold_path.read_text())
            run_improvements_cold = run_cold / "enhance-improvements-cold.md"
            run_improvements_cold.write_text(improvements_cold_path.read_text())

            moved_hub_archive = rotate_hub_to_archive(run_hub, run_archive, hub_keep)
            moved_archive_cold = rotate_archive_to_cold(
                run_archive, run_sessions_cold, archive_keep
            )
            moved_history_cold = move_old_routing_handoffs(run_hub, routing_keep)
            moved_history_sections = rotate_history_to_cold(
                run_history, run_improvements_cold, history_keep
            )
            moved_resolved_patterns = move_resolved_patterns(run_hub, run_history)
    else:
        # Step 1: Hub -> Archive
        moved_hub_archive = rotate_hub_to_archive(hub_path, archive_path, hub_keep)
        # Step 2: Archive -> Cold
        moved_archive_cold = rotate_archive_to_cold(
            archive_path, sessions_cold_path, archive_keep
        )
        # Step 3: Routing handoffs + History -> Cold
        moved_history_cold = move_old_routing_handoffs(hub_path, routing_keep)
        moved_history_sections = rotate_history_to_cold(
            history_path, improvements_cold_path, history_keep
        )
        # Step 4: Resolved patterns -> History
        moved_resolved_patterns = move_resolved_patterns(hub_path, history_path)

        # Conservation check (real run only)
        after_session_count = {
            "hub": count_session_blocks(hub_path),
            "archive": count_session_blocks(archive_path),
            "cold": count_session_blocks(sessions_cold_path),
        }
        after_history_count = (
            count_history_sections(hub_path)
            + count_history_sections(history_path)
            + count_history_sections(improvements_cold_path)
        )
        if not conservation_check(
            before_session_count,
            after_session_count,
            before_history_count,
            after_history_count,
        ):
            pr.no("CONSERVATION CHECK FAILED")
            pr.red(
                f"Before: {before_total_sessions} session blocks, {before_total_history} history sections"
            )
            pr.red(
                f"After: {sum(after_session_count.values())} session blocks, {after_history_count} history sections"
            )
            exit(1)

    # Shared summary (identical accounting for dry-run and real run)
    if dry_run:
        pr.green("DRY RUN: Compaction would move:")
    else:
        pr.yes("Compaction complete")

    if sum(moved_hub_archive.values()) > 0:
        pr.green(f"Hub -> Archive: {sum(moved_hub_archive.values())} blocks")
        for skill, count in moved_hub_archive.items():
            if count > 0:
                pr.white(f"  {skill}: {count}")

    if sum(moved_archive_cold.values()) > 0:
        pr.green(f"Archive -> Cold: {sum(moved_archive_cold.values())} blocks")
        for skill, count in moved_archive_cold.items():
            if count > 0:
                pr.white(f"  {skill}: {count}")

    if moved_history_sections > 0:
        pr.green(f"History -> Cold: {moved_history_sections} sections")

    if moved_history_cold > 0:
        pr.green(f"Routing Handoffs: {moved_history_cold} old entries dropped")

    if moved_resolved_patterns > 0:
        pr.green(f"Resolved Patterns: {moved_resolved_patterns} moved to history")

    if (
        sum(moved_hub_archive.values()) == 0
        and sum(moved_archive_cold.values()) == 0
        and moved_history_sections == 0
        and moved_history_cold == 0
        and moved_resolved_patterns == 0
    ):
        pr.white("No moves needed — files are within retention policy")


def main() -> None:
    """Main entry point."""
    import argparse

    repo_root = resolve_repo_root()

    parser = argparse.ArgumentParser(
        description="Deterministic retention/rotation tool for enhance state files."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print what would move without writing changes.",
    )

    args = parser.parse_args()

    hub_path = repo_root / "kamma" / "enhance" / "enhance-state.md"
    archive_path = (
        repo_root / "kamma" / "enhance" / "data" / "enhance-session-archive.md"
    )
    history_path = (
        repo_root / "kamma" / "enhance" / "data" / "enhance-improvements-history.md"
    )
    cold_base_path = repo_root / "kamma" / "enhance" / "archive"

    compact(
        hub_path,
        archive_path,
        history_path,
        cold_base_path,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
