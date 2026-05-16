"""Scans input/ for audio and video files, converts all to MP3, and moves originals into the output/ structure."""

import argparse
import subprocess
from pathlib import Path
from tools.printer import printer as pr

VIDEO_EXTS = {".mp4", ".mkv", ".mov"}
AUDIO_EXTS = {".wav", ".m4a", ".aiff", ".flac", ".ogg", ".opus", ".wma"}
LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


def extract_audio(src: Path, dest: Path) -> bool:
    """Extract MP3 from video using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-b:a",
        "192k",
        str(dest),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
        return result.returncode == 0
    except Exception as e:
        pr.red(f"Error extracting audio: {e}")
        return False


def convert_to_mp3(src: Path, dest: Path) -> bool:
    """Convert audio to MP3 using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-ar",
        "44100",
        "-ac",
        "2",
        "-b:a",
        "192k",
        str(dest),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
        return result.returncode == 0
    except Exception as e:
        pr.red(f"Error converting audio: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified ingest for YouTube pipeline")
    parser.add_argument("--folder", type=str, help="Specific folder in input/ to scan")
    parser.add_argument(
        "--lang",
        type=str,
        choices=["ru", "en"],
        help="Scan input/english or input/russian",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Limit number of files processed"
    )
    args = parser.parse_args()

    input_base = Path("input")
    if not input_base.exists():
        input_base.mkdir(parents=True)
        pr.amber("Created 'input/' directory. Please place files there and re-run.")
        return

    targets: list[tuple[Path, str]] = []
    if args.folder:
        targets = [(input_base / args.folder, args.folder)]
    elif args.lang:
        folder = LANG_TO_FOLDER[args.lang]
        targets = [(input_base / folder, folder)]
    else:
        # Scan all immediate subfolders
        targets = [(d, d.name) for d in sorted(input_base.iterdir()) if d.is_dir()]
        # Also include the root if there are files there
        root_files = [f for f in input_base.iterdir() if f.is_file()]
        if root_files:
            targets.insert(0, (input_base, ""))

    remaining = args.limit if args.limit > 0 else 999999

    total_processed = 0

    for target_dir, folder_name in targets:
        if not target_dir.exists():
            if args.folder or args.lang:
                pr.no(f"Directory not found: {target_dir}")
            continue

        if remaining <= 0:
            break

        pr.green_title(f"Processing: {target_dir}")

        audio_out = Path("output/audio") / folder_name
        video_out = Path("output/video") / folder_name
        audio_out.mkdir(parents=True, exist_ok=True)

        files = sorted(f for f in target_dir.iterdir() if f.is_file())

        video_found = False
        for file in files:
            if remaining <= 0:
                break

            ext = file.suffix.lower()
            if ext not in VIDEO_EXTS and ext not in AUDIO_EXTS and ext != ".mp3":
                continue

            if ext in VIDEO_EXTS:
                dest_mp3 = audio_out / file.with_suffix(".mp3").name
                dest_video = video_out / file.name

                if dest_video.exists():
                    pr.white(f"  Skipping {file.name} (video already in output)")
                    continue

                video_out.mkdir(parents=True, exist_ok=True)

                if dest_mp3.exists():
                    pr.white_tmr(f"  {file.name}")
                    file.rename(dest_video)
                    pr.yes("moved (mp3 already exists)")
                    video_found = True
                    remaining -= 1
                    total_processed += 1
                else:
                    pr.white_tmr(f"  {file.name}")
                    success = extract_audio(file, dest_mp3)
                    if success:
                        file.rename(dest_video)
                        pr.yes("extracted + moved")
                        video_found = True
                        remaining -= 1
                        total_processed += 1
                    else:
                        pr.no("failed")
            elif ext == ".mp3":
                dest = audio_out / file.name
                if dest.exists():
                    pr.white(f"  Skipping {file.name} (exists in output)")
                    continue

                file.rename(dest)
                pr.white(f"  moved: {file.name}")
                remaining -= 1
                total_processed += 1

            elif ext in AUDIO_EXTS:
                dest_mp3 = audio_out / file.with_suffix(".mp3").name
                if dest_mp3.exists():
                    pr.white(f"  Skipping {file.name} (mp3 exists)")
                    continue

                pr.white_tmr(f"  {file.name}")
                success = convert_to_mp3(file, dest_mp3)
                if success:
                    file.unlink()
                    pr.yes("converted")
                    remaining -= 1
                    total_processed += 1
                else:
                    pr.no("failed")

        if video_found:
            pr.amber(
                f"  Video files moved to output/video/{folder_name}/. "
                f"Pipeline will auto-select video mode."
            )

    pr.green(f"Ingest complete. Processed {total_processed} files.")


if __name__ == "__main__":
    main()
