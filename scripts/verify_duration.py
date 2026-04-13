#!/usr/bin/env python3
"""Verifies that the transcription length matches the audio duration to detect truncation."""

import argparse
import re
import subprocess
import sys
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
        required=True,
        help="Directory containing MD transcripts",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=120.0,
        help="Threshold in seconds to flag truncation (default: 120s)",
    )

    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    transcript_dir = Path(args.transcript_dir)

    if not transcript_dir.exists():
        print(f"Error: Transcript directory '{transcript_dir}' does not exist.")
        sys.exit(1)

    # Scans recursively for MD files
    transcript_files = sorted(list(transcript_dir.rglob("*.md")))

    if not transcript_files:
        print(f"No transcripts found in '{transcript_dir}'.")
        return

    print("\n--- Duration Verification Report ---")
    print(
        f"Checking {len(transcript_files)} transcripts against audio in '{audio_dir}'"
    )
    print(f"{'File':<50} | {'Status':<10} | {'Audio':<8} | {'MD':<8} | {'Diff'}")
    print("-" * 100)

    errors_found = 0

    for transcript_path in transcript_files:
        # Mirror structure to find audio
        relative_path = transcript_path.relative_to(transcript_dir)
        audio_path = audio_dir / relative_path.with_suffix(".mp3")

        if not audio_path.exists():
            # Try flat search if mirrored failed (fallback)
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
