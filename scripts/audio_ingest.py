#!/usr/bin/env python3
"""Universal audio ingestor: converts any audio format (including .qta) to MP3 and moves it to the output structure."""

import argparse
import subprocess
from pathlib import Path

from tools.printer import printer as pr

# Extended list of audio and video extensions to support
AUDIO_EXTS = {".wav", ".m4a", ".aiff", ".flac", ".ogg", ".opus", ".wma", ".qta", ".m4p"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".mpeg", ".mpg", ".webm"}
SUPPORTED_EXTS = AUDIO_EXTS | VIDEO_EXTS


def convert_to_mp3(src: Path, dest: Path) -> bool:
    """Convert audio or video to MP3 using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",  # Disable video (just in case it's a video file)
        "-ar",
        "44100",
        "-ac",
        "2",
        "-b:a",
        "192k",
        str(dest),
    ]
    try:
        # Using subprocess.run with capture_output to keep logs clean
        result = subprocess.run(cmd, capture_output=True, check=False)
        if result.returncode != 0:
            pr.red(
                f"Error converting {src.name}: {result.stderr.decode().splitlines()[-1]}"
            )
            return False
        return True
    except Exception as e:
        pr.red(f"Exception during conversion of {src.name}: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert any audio/video to MP3 for the transcription pipeline."
    )
    parser.add_argument(
        "--folder",
        type=str,
        required=True,
        help="Subfolder in input/ to scan (e.g., 'interview')",
    )
    parser.add_argument(
        "--input-base",
        type=str,
        default="input",
        help="Base directory for input (defaults to 'input')",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Custom output directory (defaults to output/audio/<folder>)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without actually running ffmpeg.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_base) / args.folder
    if not input_dir.exists():
        pr.no(f"Input directory not found: {input_dir}")
        return

    output_dir = (
        Path(args.output_dir) if args.output_dir else Path("output/audio") / args.folder
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in input_dir.iterdir() if f.is_file())
    total_processed = 0

    pr.green_title(f"Ingesting audio from {input_dir} to {output_dir}")

    for file in files:
        ext = file.suffix.lower()

        # Handle existing MP3s: just move them
        if ext == ".mp3":
            dest = output_dir / file.name
            if dest.exists():
                pr.white(f"  Skipping {file.name} (already in output)")
                continue

            if args.dry_run:
                pr.white(f"  [DRY RUN] Would move {file.name} → {dest}")
            else:
                file.rename(dest)
                pr.yes(f"Moved: {file.name}")
            total_processed += 1
            continue

        # Handle other supported formats: convert to MP3
        if ext in SUPPORTED_EXTS:
            dest = output_dir / file.with_suffix(".mp3").name
            if dest.exists():
                pr.white(f"  Skipping {file.name} (MP3 already exists in output)")
                # If the user wants to clean up the input, we could unlink here,
                # but for safety we keep it.
                continue

            if args.dry_run:
                pr.white(f"  [DRY RUN] Would convert {file.name} → {dest}")
            else:
                pr.white_tmr(f"  Converting {file.name}")
                pr.bip()
                if convert_to_mp3(file, dest):
                    pr.yes(f"Converted: {file.name} → {dest.name}")
                    # Remove source after successful conversion to match yt_ingest_unified behavior
                    file.unlink()
                else:
                    pr.no(f"Failed: {file.name}")
                    continue

            total_processed += 1
            continue

    pr.green(f"Ingest complete. Processed {total_processed} files.")


if __name__ == "__main__":
    main()
