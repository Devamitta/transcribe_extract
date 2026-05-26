"""Check review file for duplicate recording dates and interactively resolve conflicts."""

import argparse
import difflib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from tools.printer import printer as pr

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}
YT_HISTORY_PATH = Path("output/youtube_history.json")
TITLE_SIMILARITY_THRESHOLD = 0.95


def title_similarity(t1: str, t2: str) -> float:
    return difflib.SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


def load_yt_history(lang: str) -> dict[str, dict]:
    if not YT_HISTORY_PATH.exists():
        return {}
    data: dict[str, dict] = json.loads(YT_HISTORY_PATH.read_text(encoding="utf-8"))
    return data.get(lang, {})


def yt_status_label(stem: str, date_iso: str, history: dict[str, dict]) -> str:
    """Return upload status label for a file stem.

    Checks exact match first, then any history entry with the same date prefix.
    """
    entry = history.get(f"{stem}.mp4")
    if entry:
        return f"(uploaded: {entry['platform_id']})"
    related = [(name, e) for name, e in history.items() if name.startswith(date_iso)]
    if related:
        ids = ", ".join(e["platform_id"] for _, e in related)
        return f"(different name uploaded: {ids})"
    return "(not uploaded)"


OUTPUT_DIR_TEMPLATES: list[str] = [
    "output/audio/{folder}",
    "output/video/{folder}",
    "output/transcribed/{folder}",
    "output/thumbnails/{folder}",
]


def dd_mm_yyyy_to_iso(date_str: str) -> str:
    parts = date_str.strip().split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return ""


def parse_review_entries(review_path: Path) -> list[dict[str, str]]:
    content = review_path.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)
    entries = []
    for section in sections:
        section = section.strip()
        if "Source:" not in section:
            continue
        entry: dict[str, str] = {}
        m = re.search(r"## Source:\s*(.+)", section)
        if m:
            entry["source"] = m.group(1).strip()
            entry["stem"] = Path(entry["source"]).stem
        m = re.search(r"\*\*Recording Date:\*\*\s*([\d-]+)", section)
        if m:
            entry["recording_date"] = m.group(1).strip()
            entry["date_iso"] = dd_mm_yyyy_to_iso(entry["recording_date"])
        m = re.search(r"\*\*Suggested Title:\*\*\s*(.+)", section)
        if m:
            entry["title"] = m.group(1).strip()
        m = re.search(r"\*\*Suggested Description:\*\*\s*(.+)", section)
        if m:
            entry["description"] = m.group(1).strip()
        chapters_m = re.search(
            r"\*\*Chapters:\*\*\n((?:\[[^\]]+\][^\n]*\n?)+)", section
        )
        if chapters_m:
            entry["chapters"] = chapters_m.group(1).strip()
        if "source" in entry and entry.get("date_iso"):
            entries.append(entry)
    return entries


def find_files_for_stem(stem: str, dirs: list[Path]) -> dict[str, list[Path]]:
    """Find files matching stem (any extension) in each directory."""
    result: dict[str, list[Path]] = {}
    for d in dirs:
        if not d.exists():
            continue
        matches = [f for f in d.iterdir() if f.is_file() and f.stem == stem]
        if matches:
            result[str(d)] = matches
    return result


DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def find_transcribed_date_groups(transcribed_dir: Path) -> dict[str, list[Path]]:
    """Group .md files in transcribed_dir by YYYY-MM-DD prefix; return only groups with 2+."""
    groups: dict[str, list[Path]] = defaultdict(list)
    if not transcribed_dir.exists():
        return {}
    for f in sorted(transcribed_dir.iterdir()):
        if f.is_file() and f.suffix == ".md":
            m = DATE_RE.match(f.name)
            if m:
                groups[m.group(1)].append(f)
    return {date: files for date, files in groups.items() if len(files) > 1}


def find_files_for_date(date_iso: str, dirs: list[Path]) -> dict[str, list[Path]]:
    """Find all files starting with YYYY-MM-DD prefix in each directory."""
    result: dict[str, list[Path]] = {}
    for d in dirs:
        if not d.exists():
            continue
        matches = [
            f for f in d.iterdir() if f.is_file() and f.name.startswith(date_iso)
        ]
        if matches:
            result[str(d)] = matches
    return result


def remove_entry_from_review(review_path: Path, source_name: str) -> None:
    content = review_path.read_text(encoding="utf-8")
    sections = re.split(r"(\n---)", content)

    # Rebuild: sections alternate between separators and content
    # Format is: header [sep body] [sep body] ...
    # Split gives: [header, sep, body, sep, body, ...]
    result_parts = [sections[0]]
    i = 1
    while i < len(sections):
        sep = sections[i]
        body = sections[i + 1] if i + 1 < len(sections) else ""
        if f"## Source: {source_name}" not in body:
            result_parts.append(sep)
            result_parts.append(body)
        i += 2

    review_path.write_text("".join(result_parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find and resolve duplicate recording dates in the review file."
    )
    parser.add_argument("--lang", default="en", choices=["ru", "en"])
    parser.add_argument(
        "--dry-run", action="store_true", help="Show conflicts, don't delete"
    )
    args = parser.parse_args()

    folder = LANG_TO_FOLDER[args.lang]
    review_path = Path("reviews") / f"{folder}_review.md"

    if args.dry_run:
        pr.green(f"[DRY RUN] Review: {review_path}")

    if not review_path.exists():
        pr.no(f"Review file not found: {review_path}")
        return

    yt_history = load_yt_history(args.lang)

    found_any = False

    # --- Check review file for similar titles ---
    entries = parse_review_entries(review_path)
    if entries:
        found_pairs: list[tuple[dict, dict, float]] = []
        for i, ea in enumerate(entries):
            for eb in entries[i + 1 :]:
                title_a = ea.get("title", "")
                title_b = eb.get("title", "")
                if not title_a or not title_b:
                    continue
                ratio = title_similarity(title_a, title_b)
                if ratio >= TITLE_SIMILARITY_THRESHOLD:
                    found_pairs.append((ea, eb, ratio))

        if found_pairs:
            found_any = True
            pr.green_title(f"Found {len(found_pairs)} similar-title pair(s) in review:")

            for ea, eb, ratio in found_pairs:
                pr.green(f"\nSimilarity: {ratio:.0%}")
                yt_a = yt_status_label(ea["stem"], ea.get("date_iso", ""), yt_history)
                yt_b = yt_status_label(eb["stem"], eb.get("date_iso", ""), yt_history)
                pr.white(f"  [1] {ea.get('title', ea['stem'])}")
                pr.white(
                    f"      Date: {ea.get('recording_date', 'unknown')} | {ea['source']}  {yt_a}"
                )
                pr.white(f"  [2] {eb.get('title', eb['stem'])}")
                pr.white(
                    f"      Date: {eb.get('recording_date', 'unknown')} | {eb['source']}  {yt_b}"
                )

                if args.dry_run:
                    continue

                while True:
                    choice = input("\n  Keep which? [1/2/skip]: ").strip().lower()
                    if choice == "skip":
                        pr.amber("  Skipped.")
                        break
                    if choice in ("1", "2"):
                        remove_entry = [ea, eb][2 - int(choice)]
                        # Delete associated files
                        remove_dirs = [
                            Path(t.format(folder=folder)) for t in OUTPUT_DIR_TEMPLATES
                        ]
                        remove_files = find_files_for_stem(
                            remove_entry["stem"], remove_dirs
                        )
                        for file_list in remove_files.values():
                            for f in file_list:
                                f.unlink()
                                pr.amber(f"    Deleted: {f}")
                        remove_entry_from_review(review_path, remove_entry["source"])
                        pr.yes(f"    Removed from review: {remove_entry['source']}")
                        break
                    pr.amber("  Enter 1, 2, or 'skip'.")

    # --- Check transcribed folder for files sharing the same date prefix ---
    transcribed_dir = Path("output/transcribed") / folder
    transcribed_conflicts = find_transcribed_date_groups(transcribed_dir)

    if transcribed_conflicts:
        found_any = True
        pr.green_title(
            f"Found {len(transcribed_conflicts)} date conflict(s) in transcribed folder:"
        )

        review_sources: set[str] = set()
        if review_path.exists():
            review_sources = set(
                unicodedata.normalize("NFC", source)
                for source in re.findall(
                    r"## Source: (.+)", review_path.read_text(encoding="utf-8")
                )
            )

        for date_iso, files in sorted(transcribed_conflicts.items()):
            pr.green(f"\nDate: {date_iso}  ({len(files)} files)")
            in_review = [
                f
                for f in files
                if unicodedata.normalize("NFC", f.name) in review_sources
            ]
            not_in_review = [
                f
                for f in files
                if unicodedata.normalize("NFC", f.name) not in review_sources
            ]

            for idx, f in enumerate(files, 1):
                review_status = "(in review)" if f in in_review else "(NOT in review)"
                yt_label = yt_status_label(f.stem, date_iso, yt_history)
                pr.white(f"  [{idx}] {f.name}  {review_status}  {yt_label}")

            if args.dry_run:
                continue

            # Auto-resolve: keep the reviewed file, delete unreviewed orphans
            if in_review and not_in_review:
                for orphan in not_in_review:
                    orphan.unlink()
                    pr.yes(f"  Auto-deleted orphan: {orphan.name}")
                continue

            # Manual resolve when review status is ambiguous
            while True:
                choice = (
                    input(f"\n  Keep which? [1-{len(files)}/skip]: ").strip().lower()
                )
                if choice == "skip":
                    pr.amber("  Skipped.")
                    break
                if choice.isdigit() and 1 <= int(choice) <= len(files):
                    keep_idx = int(choice) - 1
                    for i, f in enumerate(files):
                        if i != keep_idx:
                            f.unlink()
                            pr.amber(f"    Deleted: {f.name}")
                            if unicodedata.normalize("NFC", f.name) in review_sources:
                                remove_entry_from_review(review_path, f.name)
                                pr.yes(f"    Removed from review: {f.name}")
                    break
                pr.amber(f"  Enter a number 1-{len(files)} or 'skip'.")

    if not found_any:
        pr.yes("No duplicate dates found.")
    elif not args.dry_run:
        pr.yes("Dedup complete.")


if __name__ == "__main__":
    main()
