#!/usr/bin/env python3
"""Verifies that the transcription length matches the audio duration to detect truncation."""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path


def get_audio_duration(audio_path: Path) -> float | None:
    """Returns the duration of an audio file in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        return float(result)
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"Error getting duration for {audio_path}: {e}")
        return None


def get_last_timestamp(transcript_path: Path) -> float | None:
    """Extracts the last [XX.X] timestamp from a markdown transcript (in minutes)."""
    try:
        content = transcript_path.read_text(encoding="utf-8")
        # Find all patterns like [12.3]
        matches = re.findall(r"\[(\d+(?:\.\d+)?)\]", content)
        if not matches:
            return None
        # Return the last one as a float (minutes)
        return float(matches[-1])
    except Exception as e:
        print(f"Error reading transcript {transcript_path}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Verify transcription duration against audio duration."
    )
    parser.add_argument(
        "--audio-dir",
        type=str,
        required=True,
        help="Directory containing original MP3 files",
    )
    parser.add_argument(
        "--transcript-dir",
        type=str,
        default=None,
        help="Directory containing MD transcripts (default: output/transcribed/<audio-dir-name>)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=120.0,
        help="Threshold in seconds to flag truncation (default: 120s)",
    )
    parser.add_argument(
        "--recent-minutes",
        type=int,
        default=None,
        help="Only check transcripts modified within the last N minutes (for pipelines where old audio is gone)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be verified without running ffprobe.",
    )

    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    if args.transcript_dir:
        transcript_dir = Path(args.transcript_dir)
    elif audio_dir.is_relative_to("input"):
        transcript_dir = Path("output/transcribed") / audio_dir.relative_to("input")
    else:
        transcript_dir = Path("output/transcribed")

    if args.dry_run:
        print(f"[DRY RUN] Audio:       {audio_dir}")
        print(f"[DRY RUN] Transcripts: {transcript_dir}")
        if transcript_dir.exists():
            for t in sorted(transcript_dir.rglob("*.md")):
                rel = t.relative_to(transcript_dir)
                a = audio_dir / rel.with_suffix(".mp3")
                if not a.exists():
                    a = audio_dir / t.with_suffix(".mp3").name
                print(f"  {a} ↔ {t}")
        else:
            print("  (transcript dir not yet present — pending transcription)")
        return

    if not transcript_dir.exists():
        print(f"Error: Transcript directory '{transcript_dir}' does not exist.")
        sys.exit(1)

        if not transcript_dir.exists():
            print(f"Error: Transcript directory '{transcript_dir}' does not exist.")
            sys.exit(1)

        transcript_files = sorted(list(transcript_dir.glob("*.md")))
        if not transcript_files:
            print(f"No transcripts found in '{transcript_dir}'.")
            return

    if args.dry_run:
        print(f"[DRY RUN] Audio: {audio_dir}")
        for t in transcript_files:
            a = audio_dir / t.with_suffix(".mp3").name
            print(f"  {a} ↔ {t}")
        return

    if args.recent_minutes is not None:
        cutoff = time.time() - args.recent_minutes * 60
        transcript_files = [f for f in transcript_files if f.stat().st_mtime >= cutoff]
        if not transcript_files:
            print(
                f"No transcripts modified in the last {args.recent_minutes} minutes — nothing to verify."
            )
            return

    print("\n--- Duration Verification Report ---")
    print(
        f"Checking {len(transcript_files)} transcripts against audio in '{audio_dir}'"
    )
    print(f"{'File':<50} | {'Status':<10} | {'Audio':<8} | {'MD':<8} | {'Diff'}")
    print("-" * 100)

    errors_found = 0

    for transcript_path in transcript_files:
        # Prefer mirrored structure; fall back to flat name lookup (used with --created-log)
        try:
            relative_path = transcript_path.relative_to(transcript_dir)
            audio_path = audio_dir / relative_path.with_suffix(".mp3")
        except ValueError:
            audio_path = audio_dir / "nonexistent"

        if not audio_path.exists():
            audio_path = audio_dir / transcript_path.with_suffix(".mp3").name

        if not audio_path.exists():
            print(
                f"{transcript_path.name:<50} | MISSING    | {'N/A':<8} | {'N/A':<8} | Audio not found"
            )
            continue

        audio_duration = get_audio_duration(audio_path)
        last_ts_mins = get_last_timestamp(transcript_path)

        if audio_duration is None or last_ts_mins is None:
            print(
                f"{transcript_path.name:<50} | ERROR      | {'N/A':<8} | {'N/A':<8} | Could not parse"
            )
            continue

        last_ts_secs = last_ts_mins * 60.0
        diff = audio_duration - last_ts_secs

        audio_str = f"{audio_duration / 60.0:.1f}m"
        md_str = f"{last_ts_mins:.1f}m"
        diff_str = f"{diff:.1f}s"

        if diff > args.threshold:
            status = "TRUNCATED"
            errors_found += 1
        elif diff < -30:  # Allow some small negative buffer for Whisper artifacts
            status = "SKEWED"
        else:
            status = "OK"

        print(
            f"{transcript_path.name[:50]:<50} | {status:<10} | {audio_str:<8} | {md_str:<8} | {diff_str}"
        )

    print("-" * 100)
    if errors_found > 0:
        print(f"Verification FAILED: {errors_found} potential truncation(s) detected.")
        sys.exit(1)
    else:
        print("Verification PASSED: All transcripts appear complete.")


if __name__ == "__main__":
    main()
