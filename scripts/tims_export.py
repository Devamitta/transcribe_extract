#!/usr/bin/env python3
"""Exports approved Tims Dhamma talk metadata into individual markdown files for YouTube upload descriptions."""

import argparse
import re
import subprocess
from pathlib import Path

SOURCE_AUDIO_DIR = Path("audio/tims")


def sanitize_filename(filename: str) -> str:
    """Remove characters that are not safe for filenames."""
    # We will remove: \ / : * ? " < > |
    sanitized = re.sub(r'[\\/:*?"<>|]', "", filename)
    # Also strip leading/trailing dots and spaces
    sanitized = sanitized.strip(". ")
    return sanitized


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export approved Tims Dhamma talk metadata."
    )
    parser.add_argument(
        "--review-file",
        type=str,
        help="Source of truth for approved metadata (default: latest output/tims_review_YYYY-MM-DD.md)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/audio_youtube",
        help="Directory to save approved outputs (default: output/audio_youtube)",
    )
    args = parser.parse_args()

    if args.review_file:
        review_file = Path(args.review_file)
    else:
        # Look for the latest tims_review_*.md in output/
        review_files = sorted(list(Path("output").glob("tims_review_*.md")))
        if not review_files:
            # Fallback to the old default just in case, but warn
            review_file = Path("output/tims_review.md")
        else:
            review_file = review_files[-1]

    output_dir = Path(args.output_dir)

    if not review_file.exists():
        print(f"Review file not found: {review_file}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    content = review_file.read_text(encoding="utf-8")

    # Split by separator ---
    sections = re.split(r"\n---", content)

    # The first section is the header
    items = []
    for section in sections[1:]:
        source_match = re.search(r"## Source: (.*)", section)
        title_match = re.search(r"\*\*Suggested Title:\*\* (.*)", section)
        desc_match = re.search(r"\*\*Suggested Description:\*\* (.*)", section)

        if source_match and title_match and desc_match:
            items.append(
                {
                    "source": source_match.group(1).strip(),
                    "title": title_match.group(1).strip(),
                    "description": desc_match.group(1).strip(),
                }
            )

    if not items:
        print("No approved items found in the review file.")
        return

    print(f"Exporting {len(items)} items...")

    # Find the latest date from all source files listed in the review file
    import datetime

    # Get all dates from filenames in items
    all_dates = []
    for itm in items:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", itm["source"])
        if m:
            all_dates.append(m.group(1))

    # Pick the maximum (latest) date, or fallback to today
    date_str = max(all_dates) if all_dates else datetime.date.today().isoformat()

    summary_lines = [f"# Devamitta Bhikkhu Audio, until {date_str}\n"]

    for item in items:
        sanitized_title = sanitize_filename(item["title"])
        source_stem = Path(item["source"]).stem  # strips .md extension
        source_mp3 = SOURCE_AUDIO_DIR / f"{source_stem}.mp3"
        dest_mp3 = output_dir / f"{sanitized_title}.mp3"

        if source_mp3.exists():
            # Use ffmpeg to copy audio while setting metadata (artist and title)
            # -y: overwrite; -map_metadata -1: clear old tags; -codec copy: fast (no re-encoding)
            cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source_mp3),
                "-map_metadata",
                "-1",
                "-metadata",
                f"title={item['title']}",
                "-metadata",
                "artist=Devamitta Bhikkhu",
                "-codec",
                "copy",
                str(dest_mp3),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"  Exported with metadata: {source_mp3.name} -> {dest_mp3.name}")
            except subprocess.CalledProcessError as e:
                print(f"  [ERROR] ffmpeg failed for {source_mp3.name}: {e.stderr}")
        else:
            print(f"  WARNING: source MP3 not found: {source_mp3}")

        summary_lines.append(f"\n## {item['title']}\n")
        summary_lines.append(f"**Description:** {item['description']}\n")
        summary_lines.append("\n---")

    summary_path = output_dir / "summary.md"
    summary_path.write_text("".join(summary_lines), encoding="utf-8")

    # Final verification
    source_mp3s = list(SOURCE_AUDIO_DIR.glob("*.mp3"))
    output_files = list(output_dir.iterdir())
    output_mp3s = [f for f in output_files if f.suffix == ".mp3"]
    has_summary = any(f.name == "summary.md" for f in output_files)

    print("\nVerification:")
    print(f"  Source MP3s: {len(source_mp3s)}")
    print(f"  Output MP3s: {len(output_mp3s)}")
    print(f"  summary.md present: {'Yes' if has_summary else 'No'}")

    if len(output_mp3s) == len(source_mp3s) and has_summary:
        print(f"  [OK] Export successful: {len(output_files)} total files.")
    else:
        print(
            f"  [ERROR] Count mismatch! Expected {len(source_mp3s) + 1} files, found {len(output_files)}."
        )

    print(f"\nExport complete. Results in '{output_dir}'.")


if __name__ == "__main__":
    main()
