"""Converts non-MP3 audio files in the input folder to MP3 in-place."""

import argparse
import subprocess
from pathlib import Path

from tools.printer import printer as pr


SUPPORTED_EXTENSIONS = {".wav", ".m4a", ".aiff", ".flac", ".ogg", ".opus", ".wma"}


def convert_to_mp3(file_path: Path) -> bool:
    """Converts a single audio file to MP3 and deletes the original."""
    output_path = file_path.with_suffix(".mp3")

    # If .mp3 already exists (e.g. from a previous partial run), we append a suffix
    # to avoid overwriting or getting stuck, though in-place usually means we want to replace.
    # The spec says "Run ffmpeg ... in the same directory. Verify output .mp3 exists and size > 0.
    # On success: delete the original file."

    command = [
        "ffmpeg",
        "-i",
        str(file_path),
        "-ar",
        "44100",
        "-ac",
        "2",
        "-b:a",
        "192k",
        str(output_path),
        "-y",
    ]

    try:
        # Run ffmpeg quietly but capture stderr for error reporting
        process = subprocess.run(command, capture_output=True, check=False)
        if (
            process.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 0
        ):
            file_path.unlink()
            return True
        else:
            pr.no(f"Failed: {file_path.name}")
            if process.stderr:
                pr.amber(process.stderr.decode().splitlines()[-1])
            return False
    except Exception as e:
        pr.no(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert non-MP3 audio files in the input folder to MP3 in-place."
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder in audio/ to process. If absent, scans all immediate subfolders under audio/.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N audio files (0=unlimited).",
    )
    args = parser.parse_args()

    audio_base = Path("audio")
    if not audio_base.exists():
        pr.red("Error: 'audio/' directory not found.")
        return

    targets: list[Path] = []
    if args.folder:
        folder_path = audio_base / args.folder
        if not folder_path.is_dir():
            pr.red(f"Error: Folder '{folder_path}' not found or is not a directory.")
            return
        targets = [folder_path]
    else:
        # Walk all immediate subfolders
        targets = [d for d in audio_base.iterdir() if d.is_dir()]

    if not targets:
        pr.no("No subfolders found in 'audio/' to process.")
        return

    all_files: list[Path] = []
    for target in targets:
        pr.green_title(f"Scanning: {target}")

        # Find files with supported extensions (case-insensitive)
        files = sorted(
            [f for f in target.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS]
        )

        if not files:
            pr.white(f"  No non-MP3 files found in {target}")
        all_files.extend(files)

    if args.limit > 0:
        all_files = all_files[: args.limit]

    if not all_files:
        pr.no("0 files to convert")
        return

    total_converted = 0

    for file_path in all_files:
        pr.white_tmr(f"  {file_path.name}")
        if convert_to_mp3(file_path):
            pr.yes("converted")
            total_converted += 1
        else:
            pass  # no() already printed by convert_to_mp3

    if total_converted > 0:
        pr.green(f"Converted {total_converted} files")
    else:
        pr.no("0 files to convert")


if __name__ == "__main__":
    main()
