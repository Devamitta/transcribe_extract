#!/usr/bin/env python3
"""Extracts 10-second audio snippets corresponding to Whisper anomalies for manual verification."""

import argparse
import re
import subprocess
from pathlib import Path


def extract_snippets(report_path: Path, audio_root: Path, output_dir: Path):
    """Parses the report and uses ffmpeg to extract audio snippets."""
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match filenames and their anomalies
    file_sections = re.split(r"## File: ", content)[1:]
    output_dir.mkdir(parents=True, exist_ok=True)

    for section in file_sections:
        lines = section.split("\n")
        filename = lines[0].strip()

        # Try to find the original audio file recursively
        audio_name = filename.replace(".md", ".mp3")
        audio_matches = list(audio_root.rglob(audio_name))

        if not audio_matches:
            print(f"Warning: Could not find audio file for {filename}")
            continue

        audio_file = audio_matches[0]
        anomaly_blocks = re.split(r"### Anomaly \d+: ", section)[1:]

        for idx, block in enumerate(anomaly_blocks):
            # Extract timestamp like [12.3]
            ts_match = re.search(r"\[(\d+\.\d+)\]", block)
            if not ts_match:
                continue

            timestamp_mins = float(ts_match.group(1))
            start_seconds = timestamp_mins * 60.0

            snippet_name = (
                f"{Path(filename).stem}_anomaly_{idx + 1}_at_{timestamp_mins:.1f}.mp3"
            )
            output_path = output_dir / snippet_name

            # Run ffmpeg to extract 10 seconds of audio around the anomaly
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(audio_file),
                "-ss",
                str(max(0, start_seconds - 5)),
                "-t",
                "10",
                "-c",
                "copy",
                str(output_path),
            ]

            print(f"Extracting: {snippet_name}")
            subprocess.run(cmd, capture_output=True)


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio snippets for manual verification."
    )
    parser.add_argument(
        "report", type=str, help="Path to the timestamped error report."
    )
    parser.add_argument(
        "--audio-dir", type=str, default="audio", help="Root directory for audio files."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/anomaly_snippets",
        help="Where to save snippets.",
    )
    args = parser.parse_args()

    extract_snippets(Path(args.report), Path(args.audio_dir), Path(args.output_dir))


if __name__ == "__main__":
    main()
