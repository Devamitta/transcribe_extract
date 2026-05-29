"""Creates MP4 videos from talk audio and generated thumbnail images using ffmpeg."""

import argparse
import re
import subprocess
from datetime import datetime
from pathlib import Path

from tools.dry_run import create_stub, is_pipeline_dry_run
from tools.printer import printer as pr
from tools.uploader_common import is_uploaded_in_history, load_nested_history

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}
HISTORY_PATH = Path("output/youtube_history.json")


def parse_review(review_path: Path) -> list[dict[str, str]]:
    """Parse the review markdown file for approved talks."""
    content = review_path.read_text(encoding="utf-8")
    sections = content.split("\n---")
    talks = []

    for section in sections:
        section = section.strip()
        if not section or "Source:" not in section:
            continue

        talk = {}

        # Source line
        source_match = re.search(r"Source:\s*(.+)", section)
        if source_match:
            source_full = source_match.group(1).strip()
            talk["source"] = Path(source_full).stem

        # Title
        title_match = re.search(r"\*\*Suggested Title:\*\*\s*(.+)", section)
        if title_match:
            talk["title"] = title_match.group(1).strip()

        # Approved field
        approved_m = re.search(r"\*\*Approved:\*\*\s*(yes|no)", section, re.IGNORECASE)
        talk["approved"] = approved_m.group(1).lower() == "yes" if approved_m else False

        # Recording Date (DD-MM-YYYY)
        date_match = re.search(r"\*\*Recording Date:\*\*\s*([\d-]+)", section)
        if date_match:
            talk["recording_date"] = date_match.group(1).strip()

        if (
            "title" in talk
            and "source" in talk
            and talk.get("recording_date")
            and talk.get("approved")
        ):
            talks.append(talk)

    return talks


def _parse_date(t: dict[str, str]) -> datetime:
    try:
        return datetime.strptime(t["recording_date"], "%d-%m-%Y")
    except (ValueError, KeyError):
        return datetime.min


def main() -> None:
    parser = argparse.ArgumentParser(description="Create MP4 videos for YouTube.")
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
    parser.add_argument("--review-file", type=Path, help="Path to specific review file")
    parser.add_argument(
        "--audio-dir",
        type=Path,
        help="Directory containing source MP3 files",
    )
    parser.add_argument(
        "--thumbnails-dir",
        type=Path,
        help="Directory containing thumbnail images",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for MP4 videos",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't run ffmpeg, just show what would be done",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N talks (0=unlimited).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Create videos even when YouTube history marks them uploaded.",
    )

    args = parser.parse_args()

    transcribed_base = Path("output/transcribed")

    if args.folder is not None:
        folder_names = [args.folder]
    elif args.lang:
        folder_names = [LANG_TO_FOLDER[args.lang]]
    else:
        folder_names = [d.name for d in transcribed_base.iterdir() if d.is_dir()]

    if not folder_names:
        pr.no("No subfolders found in 'output/transcribed/'.")
        return

    # Pass 1: collect all approved talks from all folders
    all_talks: list[tuple[str, dict, Path, Path, Path]] = []
    lang_folder = LANG_TO_FOLDER.get(args.lang or "en", "english")
    for folder_name in folder_names:
        review_path = args.review_file or Path("reviews") / f"{lang_folder}_review.md"
        if not review_path or not review_path.exists():
            if args.folder:
                pr.no(f"  Review file not found at '{review_path}'.")
            continue

        audio_dir = args.audio_dir or Path("output/audio") / folder_name
        thumbnails_dir = args.thumbnails_dir or Path("output/thumbnails") / folder_name
        output_dir = args.output_dir or Path("output/video") / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        talks = parse_review(review_path)
        if not talks:
            continue
        talks.sort(key=_parse_date)
        for talk in talks:
            all_talks.append((folder_name, talk, audio_dir, thumbnails_dir, output_dir))

    # Apply global limit
    if args.limit > 0:
        all_talks = all_talks[: args.limit]

    if not all_talks:
        pr.no("No approved talks found to process.")
        return

    history = load_nested_history(HISTORY_PATH, args.lang or "en")
    if not args.force:
        all_talks = [
            item
            for item in all_talks
            if not is_uploaded_in_history(history, f"{item[1]['source']}.mp4")
        ]

    if not all_talks:
        pr.green("All approved talks are already uploaded.")
        return

    # Pass 2: process
    existing = sum(
        1 for _, talk, _, _, od in all_talks if (od / f"{talk['source']}.mp4").exists()
    )
    new_count = len(all_talks) - existing
    pr.green_title(
        f"Creating {new_count} of {len(all_talks)} videos ({existing} already exist)..."
    )
    created, skipped, errors = 0, 0, 0

    for folder_name, talk, audio_dir, thumbnails_dir, output_dir in all_talks:
        source = talk["source"]
        title = talk["title"]

        audio_path = audio_dir / f"{source}.mp3"
        image_path = thumbnails_dir / f"{source}.jpg"
        output_mp4 = output_dir / f"{source}.mp4"

        if not audio_path.exists():
            pr.amber(f"    Audio not found: {audio_path.name}")
            errors += 1
            continue

        if not image_path.exists():
            pr.amber(f"    Thumbnail not found: {image_path.name}")
            errors += 1
            continue

        if output_mp4.exists():
            skipped += 1
            continue

        if args.dry_run:
            pr.white(f"  [DRY RUN] {audio_path} + {image_path} → {output_mp4}")
            if is_pipeline_dry_run():
                create_stub(output_mp4)
            continue

        # ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-stats",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-metadata",
            f"title={title}",
            "-metadata",
            "artist=Devamitta Bhikkhu",
            "-shortest",
            str(output_mp4),
        ]

        pr.amber(f"    Encoding [{folder_name}]: {title}...")
        pr.bip()
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            final_stats = ""
            for part in re.split(r"[\r\n]+", result.stderr):
                part = part.strip()
                if not part:
                    continue
                if "time=" in part and "bitrate=" in part:
                    final_stats = part
                else:
                    pr.amber(f"    ffmpeg: {part}")
            if result.returncode != 0:
                pr.no(f"    ffmpeg failed: {source}")
                errors += 1
            else:
                if final_stats:
                    pr.cyan(f"    {final_stats}")
                pr.yes(f"    Created: {output_mp4.name}")
                created += 1
        except Exception as e:
            pr.no(f"    Error: {e}")
            errors += 1

    pr.green(f"Done: {created} created, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
