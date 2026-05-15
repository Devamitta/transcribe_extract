"""Exports approved audio or video with embedded metadata based on the review file."""

import argparse
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path

from tools.printer import printer as pr
from tools.uploader_common import find_latest_review

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def sanitize_filename(name: str) -> str:
    """Removes invalid filename characters and cleans up whitespace."""
    sanitized = re.sub(r'[\\/:*?"<>]', "", name)
    sanitized = sanitized.replace("|", "-")
    sanitized = re.sub(r"\s{2,}", " ", sanitized)
    return sanitized.strip(". ")


def parse_date(date_str: str) -> datetime | None:
    """Parses DD-MM-YYYY date format."""
    try:
        return datetime.strptime(date_str.strip(), "%d-%m-%Y")
    except ValueError:
        return None


def check_approvals(review_file: Path, folder_name: str) -> bool:
    """Checks if all entries with recording dates are approved. Returns True if all OK."""
    if not review_file.exists():
        return True

    content = review_file.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)

    unapproved = []
    # Skip header
    for section in sections[1:]:
        source_m = re.search(r"## Source: (.+)", section)
        if not source_m:
            continue

        source = source_m.group(1).strip()
        # Skip entries without a recording date (they are ignored by export anyway)
        date_m = re.search(r"\*\*Recording Date:\*\*\s*(\d.*)", section)
        if not date_m:
            continue

        approved_m = re.search(r"\*\*Approved:\*\*\s*(yes|no)", section, re.IGNORECASE)
        if not approved_m or approved_m.group(1).lower() != "yes":
            unapproved.append(source)

    if unapproved:
        pr.no("Export blocked: entries not yet approved:")
        for source in unapproved:
            pr.amber(f"  - {source}")
        pr.amber(
            f"Open reviews/{folder_name}_review.md, set Approved: yes for each reviewed entry, then re-run."
        )
        return False

    return True


def rename_step(
    review_file: Path,
    transcript_dir: Path,
    source_audio_dir: Path,
    video_dir: Path,
    video_mode: bool,
    dry_run: bool,
) -> None:
    """Rename source files in original folders to 'YYYY-MM-DD - Suggested Title'."""
    if not review_file.exists():
        return

    content = review_file.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)

    dated: list[tuple[str, str, datetime, str]] = []
    # Skip the first section (header)
    for section in sections[1:]:
        source_match = re.search(r"## Source: (.+)", section)
        date_match = re.search(r"\*\*Recording Date:\*\* (.+)", section)
        title_match = re.search(r"\*\*Suggested Title:\*\* (.+)", section)
        if not source_match:
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
        return

    dated.sort(key=lambda x: x[2])

    renamed: list[tuple[str, str]] = []
    skipped = 0

    for source_name, iso_date, _dt, title_raw in dated:
        old_stem = Path(source_name).stem
        new_stem = f"{iso_date} - {sanitize_filename(title_raw)}"

        if old_stem == new_stem:
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
            pr.green(f"      [dry-run] {source_name} → {new_md_name}")
            renamed.append((source_name, new_md_name))
            continue

        if not old_md.exists():
            pr.amber(f"      Transcript not found: {old_md}")
            continue

        old_md.rename(new_md)
        if old_mp3.exists():
            old_mp3.rename(new_mp3)

        if video_mode and old_mp4.exists():
            old_mp4.rename(new_mp4)

        pr.green(f"  {source_name} → {new_md_name}")
        renamed.append((source_name, new_md_name))

    if renamed and not dry_run:
        updated = content
        for old_name, new_name in renamed:
            updated = updated.replace(
                f"## Source: {old_name}", f"## Source: {new_name}"
            )
        review_file.write_text(updated, encoding="utf-8")

    if renamed:
        verb = "Would rename" if dry_run else "Renamed"
        pr.green(f"{verb} {len(renamed)} file(s)")


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
    args = parser.parse_args()

    transcribed_base = Path("output/transcribed")
    audio_base = Path("audio")
    video_base = Path("video")

    if args.folder:
        folder_names = [args.folder]
    elif args.lang:
        folder_names = [LANG_TO_FOLDER[args.lang]]
    else:
        folder_names = [d.name for d in transcribed_base.iterdir() if d.is_dir()]

    if not folder_names:
        pr.no("No subfolders found in 'output/transcribed/'.")
        return

    all_items: list[tuple[str, dict, Path, Path, Path]] = []

    for folder_name in folder_names:
        transcript_dir = transcribed_base / folder_name
        source_audio_dir = audio_base / folder_name
        video_dir = video_base / folder_name

        review_path = args.review_file or find_latest_review(
            f"{folder_name}_review*.md"
        )
        if not review_path or not review_path.exists():
            pr.amber(f"  No review file found for '{folder_name}'. skipping.")
            continue

        if not args.dry_run and not check_approvals(review_path, folder_name):
            sys.exit(1)

        # Step 1: Rename source files in their original folders
        rename_step(
            review_path,
            transcript_dir,
            source_audio_dir,
            video_dir,
            args.video_mode,
            args.dry_run,
        )

        if args.dry_run:
            continue

        # Determine output directory
        output_dir = args.output_dir
        if not output_dir:
            suffix = "_video_upload" if args.video_mode else "_audio"
            output_dir = Path("output") / f"{folder_name}{suffix}"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Read approved entries and collect items
        content = review_path.read_text(encoding="utf-8")
        sections = re.split(r"\n---", content)

        for section in sections[1:]:
            source_match = re.search(r"## Source: (.*)", section)
            title_match = re.search(r"\*\*Suggested Title:\*\* (.*)", section)
            desc_match = re.search(r"\*\*Suggested Description:\*\* (.*)", section)
            date_match = re.search(r"\*\*Recording Date:\*\* (.*)", section)

            if not (source_match and title_match and desc_match):
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

    if not all_items:
        pr.no("No dated items found to process.")
        return

    exported, errors = 0, 0

    for folder_name, item, source_audio_dir, video_dir, output_dir in all_items:
        source_stem = Path(item["source"]).stem

        if args.video_mode:
            source_file = video_dir / f"{source_stem}.mp4"
            dest_file = output_dir / f"{source_stem}.mp4"
        else:
            source_file = source_audio_dir / f"{source_stem}.mp3"
            dest_file = output_dir / f"{source_stem}.mp3"

        if source_file.exists():
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
                "artist=Devamitta Bhikkhu",
                "-metadata",
                f"date={item['recording_date']}",
                "-c",
                "copy",
                str(dest_file),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                exported += 1
            except subprocess.CalledProcessError as e:
                pr.no(f"  ffmpeg failed for {source_file.name}: {e.stderr}")
                errors += 1
        else:
            pr.amber(f"  Source file not found: {source_file}")
            errors += 1

    pr.green(f"Done: Exported: {exported} | Errors: {errors}")


if __name__ == "__main__":
    main()
