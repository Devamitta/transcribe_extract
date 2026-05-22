"""Exports approved audio or video with embedded metadata based on the review file."""

import argparse
import re
import subprocess
from datetime import datetime
from pathlib import Path

from tools.dry_run import is_pipeline_dry_run, is_stub, log_stub
from tools.printer import printer as pr

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}

SORT_SAFETY_FIELDS: list[str] = [
    "## Source:",
    "**Recording Date:**",
    "**Approved:**",
    "**Suggested Title:**",
    "**Suggested Description:**",
    "**Suggested Tags:**",
    "**Chapters:**",
]


DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def sanitize_filename(name: str) -> str:
    """Removes invalid filename characters and cleans up whitespace."""
    sanitized = name.replace("|", "-")
    sanitized = re.sub(r"\s*:\s*", " - ", sanitized)
    sanitized = re.sub(r'[\\/:*?"<>]', "", sanitized)
    sanitized = re.sub(r"\s{2,}", " ", sanitized)
    return sanitized.strip(". ")


def parse_date(date_str: str) -> datetime | None:
    """Parses DD-MM-YYYY date format."""
    try:
        return datetime.strptime(date_str.strip(), "%d-%m-%Y")
    except ValueError:
        return None


def rename_step(
    review_file: Path,
    transcript_dir: Path,
    source_audio_dir: Path,
    video_dir: Path,
    video_mode: bool,
    dry_run: bool,
) -> list[Path]:
    """Rename source files in original folders to 'YYYY-MM-DD - Suggested Title'."""
    if not review_file.exists():
        return []

    content = review_file.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)

    dated: list[tuple[str, str, datetime, str]] = []
    # Skip the first section (header)
    for section in sections[1:]:
        source_match = re.search(r"## Source: (.+)", section)
        date_match = re.search(r"\*\*Recording Date:\*\* (.+)", section)
        title_match = re.search(r"\*\*Suggested Title:\*\* (.+)", section)
        approved_match = re.search(
            r"\*\*Approved:\*\*\s*(yes|no)", section, re.IGNORECASE
        )

        if not source_match:
            continue

        if not approved_match or approved_match.group(1).lower() != "yes":
            continue

        source = source_match.group(1).strip()
        date_raw = date_match.group(1).strip() if date_match else ""
        title_raw = title_match.group(1).strip() if title_match else ""

        if not date_raw or not title_raw:
            continue

        parsed = parse_date(date_raw)
        if parsed is None:
            pr.amber(f"    Cannot parse date '{date_raw}' for '{source}' — skipping.")
            continue
        dated.append((source, parsed.strftime("%Y-%m-%d"), parsed, title_raw))

    if not dated:
        return []

    dated.sort(key=lambda x: x[2])

    renamed: list[tuple[str, str]] = []
    renamed_media_paths: list[Path] = []
    skipped = 0

    for source_name, iso_date, _dt, title_raw in dated:
        old_stem = Path(source_name).stem
        new_stem = f"{iso_date} - {sanitize_filename(title_raw)}"

        if old_stem == new_stem:
            # Already correctly named; still record path so the upload filter works on re-runs.
            if video_mode:
                _mp4 = video_dir / f"{old_stem}.mp4"
                if _mp4.exists():
                    renamed_media_paths.append(_mp4)
            else:
                _mp3 = source_audio_dir / f"{old_stem}.mp3"
                if _mp3.exists():
                    renamed_media_paths.append(video_dir / f"{old_stem}.mp4")
            skipped += 1
            continue
        new_md_name = f"{new_stem}.md"
        old_md = transcript_dir / source_name
        new_md = transcript_dir / new_md_name

        # Audio always exists (or should)
        old_mp3 = source_audio_dir / f"{old_stem}.mp3"
        new_mp3 = source_audio_dir / f"{new_stem}.mp3"

        # Video only if video mode
        old_mp4 = video_dir / f"{old_stem}.mp4"
        new_mp4 = video_dir / f"{new_stem}.mp4"

        if dry_run:
            pr.white(f"  [DRY RUN] {old_md} → {new_md}")
            if video_mode:
                pr.white(f"           {old_mp4} → {new_mp4}")
            pr.white(f"           {old_mp3} → {new_mp3}")
            if is_pipeline_dry_run() and is_stub(old_md):
                old_md.rename(new_md)
                log_stub(new_md)
                if is_stub(old_mp3):
                    old_mp3.rename(new_mp3)
                    log_stub(new_mp3)
                    if not video_mode:
                        renamed_media_paths.append(new_mp3)
                if video_mode and is_stub(old_mp4):
                    old_mp4.rename(new_mp4)
                    log_stub(new_mp4)
                    renamed_media_paths.append(new_mp4)
            else:
                # Real files in dry-run: record current path so upload filter
                # can match the file as it exists on disk (not yet renamed).
                if video_mode:
                    renamed_media_paths.append(old_mp4)
                else:
                    renamed_media_paths.append(old_mp3)
            renamed.append((source_name, new_md_name))
            continue

        if not old_md.exists():
            pr.amber(f"      Transcript not found: {old_md}")
            continue

        old_md.rename(new_md)
        if old_mp3.exists():
            old_mp3.rename(new_mp3)
            if not video_mode:
                renamed_media_paths.append(video_dir / f"{new_stem}.mp4")

        if video_mode and old_mp4.exists():
            old_mp4.rename(new_mp4)
            renamed_media_paths.append(new_mp4)

        pr.green(f"  {source_name} → {new_md_name}")
        renamed.append((source_name, new_md_name))

    if renamed and not dry_run:
        updated = content
        for old_name, new_name in renamed:
            updated = updated.replace(
                f"## Source: {old_name}", f"## Source: {new_name}"
            )
        review_file.write_text(updated, encoding="utf-8")

    if renamed and dry_run and is_pipeline_dry_run():
        # Update source names in the review file so downstream dry-run scripts find the renamed stubs.
        # Only touches sections that carry the [DRY_RUN] marker — real entries are never modified.
        sections = content.split("\n---")
        changed = False
        for idx, section in enumerate(sections):
            for old_name, new_name in renamed:
                if f"## Source: {old_name}" in section and "[DRY_RUN]" in section:
                    sections[idx] = section.replace(
                        f"## Source: {old_name}", f"## Source: {new_name}"
                    )
                    changed = True
        if changed:
            review_file.write_text("\n---".join(sections), encoding="utf-8")

    if renamed:
        verb = "Would rename" if dry_run else "Renamed"
        pr.green(f"{verb} {len(renamed)} file(s)")

    return renamed_media_paths


def sort_review_file(review_file: Path, dry_run: bool) -> None:
    """Sort review file sections by recording date; undated entries go last."""
    if not review_file.exists():
        return

    content = review_file.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)

    if len(sections) <= 2:
        return

    header = sections[0]
    body_sections = sections[1:]

    def sort_key(section: str) -> tuple[int, datetime]:
        date_match = re.search(r"\*\*Recording Date:\*\* (.+)", section)
        if not date_match:
            return (1, datetime.min)
        parsed = parse_date(date_match.group(1).strip())
        if parsed is None:
            return (1, datetime.min)
        return (0, parsed)

    sorted_sections = sorted(body_sections, key=sort_key)

    sorted_content = "\n---".join([header] + sorted_sections)
    mismatches = [
        f"'{f}': {content.count(f)} → {sorted_content.count(f)}"
        for f in SORT_SAFETY_FIELDS
        if content.count(f) != sorted_content.count(f)
    ]
    if mismatches:
        for msg in mismatches:
            pr.no(f"  Sort safety check failed: {msg}")
        return

    if sorted_sections == body_sections:
        pr.green("  Review file already sorted by date")
        return

    if dry_run:
        pr.green("  [dry-run] Would sort review file by recording date")
        return

    review_file.write_text(sorted_content, encoding="utf-8")
    pr.green("  Sorted review file by recording date")


def sort_review_file(review_file: Path, dry_run: bool) -> None:
    """Sort review file sections by recording date; undated entries go last."""
    if not review_file.exists():
        return

    content = review_file.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)

    if len(sections) <= 2:
        return

    header = sections[0]
    body_sections = sections[1:]

    def sort_key(section: str) -> tuple[int, datetime]:
        date_match = re.search(r"\*\*Recording Date:\*\* (.+)", section)
        if not date_match:
            return (1, datetime.min)
        parsed = parse_date(date_match.group(1).strip())
        if parsed is None:
            return (1, datetime.min)
        return (0, parsed)

    sorted_sections = sorted(body_sections, key=sort_key)

    sorted_content = "\n---".join([header] + sorted_sections)
    mismatches = [
        f"'{f}': {content.count(f)} → {sorted_content.count(f)}"
        for f in SORT_SAFETY_FIELDS
        if content.count(f) != sorted_content.count(f)
    ]
    if mismatches:
        for msg in mismatches:
            pr.no(f"  Sort safety check failed: {msg}")
        return

    if sorted_sections == body_sections:
        pr.green("  Review file already sorted by date")
        return

    if dry_run:
        pr.green("  [dry-run] Would sort review file by recording date")
        return

    review_file.write_text(sorted_content, encoding="utf-8")
    pr.green("  Sorted review file by recording date")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rename source files and export approved audio or video with metadata."
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder in output/transcribed/ to process. If absent and --lang given, defaults to lang-based folder. If both absent, scans all subfolders.",
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=["ru", "en"],
        help="Language shortcode (ru|en). Sets default folder (ru→russian, en→english). Overridden by --folder.",
    )
    parser.add_argument(
        "--video-mode",
        action="store_true",
        help="Export video (.mp4) instead of audio (.mp3).",
    )
    parser.add_argument(
        "--review-file",
        type=Path,
        help="Override review file path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override output directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview renames without making changes; skips export.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N dated items (0=unlimited).",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Artist name override for metadata",
    )
    parser.add_argument(
        "--created-log",
        type=Path,
        help="Write renamed media file paths to this file (one per line).",
    )
    args = parser.parse_args()

    transcribed_base = Path("output/transcribed")
    audio_base = Path("output/audio")
    video_base = Path("output/video")

    # Artist name based on lang or override
    artist_name = args.name
    if not artist_name:
        artist_name = "Бхиккху Дэвамитта" if args.lang == "ru" else "Bhikkhu Devamitta"

    if args.folder is not None:
        folder_names = [args.folder]
    elif args.lang:
        folder_names = [LANG_TO_FOLDER[args.lang]]
    else:
        folder_names = [d.name for d in transcribed_base.iterdir() if d.is_dir()]

    if not folder_names:
        pr.no("No subfolders found in 'output/transcribed/'.")
        return

    all_items: list[tuple[str, dict, Path, Path, Path]] = []
    all_renamed_media: list[Path] = []

    for folder_name in folder_names:
        transcript_dir = transcribed_base / folder_name
        source_audio_dir = audio_base / folder_name
        video_dir = video_base / folder_name

        lang_folder = LANG_TO_FOLDER.get(args.lang or "en", "english")
        review_path = args.review_file or Path("reviews") / f"{lang_folder}_review.md"

        if not review_path or not review_path.exists():
            pr.amber(f"  No review file found at '{review_path}'. skipping.")
            continue

        # Step 1: Rename source files in their original folders
        renamed_media = rename_step(
            review_path,
            transcript_dir,
            source_audio_dir,
            video_dir,
            args.video_mode,
            args.dry_run,
        )
        sort_review_file(review_path, args.dry_run)

        stats_content = review_path.read_text(encoding="utf-8")
        stats_sections = re.split(r"\n---", stats_content)[1:]
        total = sum(1 for s in stats_sections if re.search(r"## Source:", s))
        with_date = sum(
            1 for s in stats_sections if re.search(r"\*\*Recording Date:\*\* \S", s)
        )
        approved = sum(
            1
            for s in stats_sections
            if re.search(r"\*\*Approved:\*\*\s*yes", s, re.IGNORECASE)
        )
        pr.green(
            f"  Entries: {total} total | {with_date} with date | {approved} approved"
        )

        if args.dry_run:
            continue

        # Determine output directory (same as source for in-place embed)
        output_dir = args.output_dir
        if not output_dir:
            if args.video_mode:
                output_dir = Path("output/video") / folder_name
            else:
                output_dir = Path("output/audio") / folder_name

        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Read approved entries and collect items
        content = review_path.read_text(encoding="utf-8")
        sections = re.split(r"\n---", content)

        for section in sections[1:]:
            source_match = re.search(r"## Source: (.*)", section)
            title_match = re.search(r"\*\*Suggested Title:\*\* (.*)", section)
            desc_match = re.search(
                r"\*\*Suggested Description:\*\*\s*(.*?)(?=\n\*\*Suggested Tags:|\Z)",
                section,
                re.DOTALL,
            )
            date_match = re.search(r"\*\*Recording Date:\*\* (.*)", section)
            approved_m = re.search(
                r"\*\*Approved:\*\*\s*(yes|no)", section, re.IGNORECASE
            )

            if not (source_match and title_match and desc_match):
                continue

            if not approved_m or approved_m.group(1).lower() != "yes":
                continue

            recording_date = date_match.group(1).strip() if date_match else ""
            if recording_date:
                item = {
                    "source": source_match.group(1).strip(),
                    "title": title_match.group(1).strip(),
                    "description": desc_match.group(1).strip(),
                    "recording_date": recording_date,
                }
                all_items.append(
                    (folder_name, item, source_audio_dir, video_dir, output_dir)
                )

    # Apply global limit
    if args.limit > 0:
        all_items = all_items[: args.limit]

    if args.created_log and all_renamed_media:
        args.created_log.write_text(
            "\n".join(str(p) for p in all_renamed_media) + "\n",
            encoding="utf-8",
        )

    if not all_items:
        if not args.dry_run:
            pr.no("No dated items found to process.")
        return

    exported, errors = 0, 0

    for folder_name, item, source_audio_dir, video_dir, output_dir in all_items:
        source_stem = Path(item["source"]).stem

        if args.video_mode:
            source_file = video_dir / f"{source_stem}.mp4"
        else:
            source_file = source_audio_dir / f"{source_stem}.mp3"

        if source_file.exists():
            tmp_file = source_file.with_suffix(".tmp" + source_file.suffix)
            cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source_file),
                "-map_metadata",
                "-1",
                "-metadata",
                f"title={item['title']}",
                "-metadata",
                f"artist={artist_name}",
                "-metadata",
                f"date={item['recording_date']}",
                "-metadata",
                f"description={item['description']}",
                "-c",
                "copy",
                str(tmp_file),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                tmp_file.rename(source_file)
                exported += 1
            except subprocess.CalledProcessError as e:
                pr.no(f"  ffmpeg failed for {source_file.name}: {e.stderr}")
                if tmp_file.exists():
                    tmp_file.unlink()
                errors += 1
        else:
            pr.amber(f"  Source file not found: {source_file}")
            errors += 1

    pr.green(f"Done: Exported: {exported} | Errors: {errors}")


if __name__ == "__main__":
    main()
