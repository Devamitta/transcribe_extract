"""Extracts MP3 audio from video files for pipeline ingestion."""

import argparse
import subprocess
from pathlib import Path

from tools.printer import printer as pr


def extract_audio(video_path: Path, audio_path: Path) -> bool:
    """Extracts MP3 audio from a video file."""
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-b:a",
        "192k",
        str(audio_path),
        "-y",
    ]

    try:
        process = subprocess.run(command, capture_output=True, check=False)
        if (
            process.returncode == 0
            and audio_path.exists()
            and audio_path.stat().st_size > 0
        ):
            return True
        else:
            pr.no(f"Failed: {video_path.name}")
            if process.stderr:
                pr.amber(process.stderr.decode().splitlines()[-1])
            return False
    except Exception as e:
        pr.no(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Extracts MP3 audio from video files for pipeline ingestion."
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder in video/ to process. If absent, scans all immediate subfolders under video/.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N video files (0=unlimited).",
    )
    args = parser.parse_args()

    video_base = Path("video")
    if not video_base.exists():
        pr.red("Error: 'video/' directory not found.")
        return

    targets: list[Path] = []
    if args.folder:
        folder_path = video_base / args.folder
        if not folder_path.is_dir():
            pr.red(f"Error: Folder '{folder_path}' not found or is not a directory.")
            return
        targets = [folder_path]
    else:
        # Walk all immediate subfolders
        targets = [d for d in video_base.iterdir() if d.is_dir()]

    if not targets:
        pr.no("No subfolders found in 'video/' to process.")
        return

    all_video_files: list[Path] = []
    for target in targets:
        pr.green_title(f"Scanning: {target}")

        # Find .mp4 files (case-insensitive)
        files = sorted(list(target.rglob("*.mp4")) + list(target.rglob("*.MP4")))

        if not files:
            pr.white(f"  No .mp4 files found in {target}")
        all_video_files.extend(files)

    if args.limit > 0:
        all_video_files = all_video_files[: args.limit]

    if not all_video_files:
        pr.no("No video files found to process.")
        return

    total_extracted = 0

    for video_path in all_video_files:
        # Determine output audio path: audio/{subfolder}/{stem}.mp3
        # We need to preserve the relative path from video_base
        relative_path = video_path.relative_to(video_base)
        audio_path = Path("audio") / relative_path.with_suffix(".mp3")

        if audio_path.exists():
            pr.white(f"  Skipping {video_path.name} (audio already exists)")
            continue

        pr.white_tmr(f"  {video_path.name}")
        if extract_audio(video_path, audio_path):
            pr.yes("extracted")
            total_extracted += 1
        else:
            pass  # no() already printed by extract_audio

    if total_extracted > 0:
        pr.green(f"Extracted {total_extracted} audio files")
    else:
        pr.no("0 audio files extracted")


if __name__ == "__main__":
    main()
