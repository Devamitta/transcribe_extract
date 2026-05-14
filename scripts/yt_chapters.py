"""Generates AI chapter timestamps for Dhamma talk transcripts and appends them to the review file."""

import argparse
import concurrent.futures
import re
import subprocess
import time
from pathlib import Path

from tools.printer import printer as pr
from tools.provider import (
    build_cacheable_contents,
    generate_with_timeout,
    get_working_key,
)


SNAP_TOLERANCE_MINS = 2.0
SILENCE_SNAP_TOLERANCE_MINS = 3.0
MIN_CHAPTER_GAP_MINS = 2.0
MIN_CHAPTERS = 3
SILENCE_NOISE_DB_LEVELS = [-30, -25, -20]
SILENCE_MIN_DURATION_S = 1.5

SYSTEM_INSTRUCTIONS_PARAGRAPHS: dict[str, str] = {
    "ru": """You are analyzing a timestamped transcript of a Russian Buddhist Dhamma talk.

Transcript format:
[X.X] paragraph text...

X.X is the paragraph start time in MINUTES (decimal). These are the ONLY valid timestamps.

Your task: identify 5–12 meaningful topic sections and name each one.

Rules:
- The FIRST chapter MUST use the exact timestamp [0.0] — hard requirement for YouTube
- Copy timestamps EXACTLY as they appear in the transcript — do NOT invent new ones
- Chapter names: Russian, 2–5 words, concise and descriptive of the actual content
- Aim for 6–10 chapters for a 45–60 minute talk; fewer for shorter talks
- Each chapter must span at least 2–3 minutes of content

Output format — one chapter per line, nothing else, no explanations, no markdown:
[0.0] Название первой главы
[X.X] Название следующей главы
""",
    "en": """You are analyzing a timestamped transcript of an English Buddhist Dhamma talk.

Transcript format:
[X.X] paragraph text...

X.X is the paragraph start time in MINUTES (decimal). These are the ONLY valid timestamps.

Your task: identify 5–12 meaningful topic sections and name each one.

Rules:
- The FIRST chapter MUST use the exact timestamp [0.0] — hard requirement for YouTube
- Copy timestamps EXACTLY as they appear in the transcript — do NOT invent new ones
- Chapter names: English, 2–5 words, concise and descriptive of the actual content
- Aim for 6–10 chapters for a 45–60 minute talk; fewer for shorter talks
- Each chapter must span at least 2–3 minutes of content

Output format — one chapter per line, nothing else, no explanations, no markdown:
[0.0] Name of the first chapter
[X.X] Name of the next chapter
""",
}


def build_silence_instruction(
    silence_times: list[float], lang: str, duration_mins: float = 0.0
) -> str:
    """Build system instruction that pins the LLM to real silence break points."""
    min_ch, max_ch = compute_chapter_range(duration_mins, len(silence_times))
    ts_list = "  ".join(f"[{t:.2f}]" for t in silence_times)

    if lang == "ru":
        return f"""You are analyzing a Russian Buddhist Dhamma talk.

The following timestamps mark actual silence/pause points in the audio (in MINUTES).
These are the ONLY valid chapter start times — do NOT use any other values:
{ts_list}

The transcript below is provided for content understanding only.
Do NOT use timestamps from the transcript — use ONLY the timestamps listed above.

Your task: identify {min_ch}–{max_ch} meaningful topic sections and name each one.

Rules:
- The FIRST chapter MUST be [0.00] — always in the list above
- Select timestamps from the list that best match topic transitions in the talk
- Chapter names: Russian, 2–5 words, concise and descriptive of the actual content
- Aim for {max_ch} chapters; use fewer if the talk is short
- Each chapter must span at least 2–3 minutes of content

Output format — one chapter per line, nothing else, no explanations, no markdown:
[0.00] Название первой главы
[X.XX] Название следующей главы
"""
    else:
        return f"""You are analyzing an English Buddhist Dhamma talk.

The following timestamps mark actual silence/pause points in the audio (in MINUTES).
These are the ONLY valid chapter start times — do NOT use any other values:
{ts_list}

The transcript below is provided for content understanding only.
Do NOT use timestamps from the transcript — use ONLY the timestamps listed above.

Your task: identify {min_ch}–{max_ch} meaningful topic sections and name each one.

Rules:
- The FIRST chapter MUST be [0.00] — always in the list above
- Select timestamps from the list that best match topic transitions in the talk
- Chapter names: English, 2–5 words, concise and descriptive of the actual content
- Aim for {max_ch} chapters; use fewer if the talk is short
- Each chapter must span at least 2–3 minutes of content

Output format — one chapter per line, nothing else, no explanations, no markdown:
[0.00] Name of the first chapter
[X.XX] Name of the next chapter
"""


def extract_timestamps(text: str) -> list[float]:
    """Extracts all [X.X] decimal minute timestamps from the transcript text."""
    return sorted({float(m) for m in re.findall(r"\[(\d+(?:\.\d+)?)\]", text)})


def detect_silences(
    audio_path: Path, noise_db: int = SILENCE_NOISE_DB_LEVELS[0]
) -> list[float]:
    """Return silence start times in minutes using ffmpeg silencedetect."""
    cmd = [
        "ffmpeg",
        "-i",
        str(audio_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={SILENCE_MIN_DURATION_S}",
        "-f",
        "null",
        "-",
    ]
    # Use errors='replace' to handle truncated UTF-8 in metadata
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    output = result.stderr  # ffmpeg writes filter output to stderr
    times_s: list[float] = []
    for line in output.splitlines():
        if "silence_start:" in line:
            m = re.search(r"silence_start:\s*([\d.]+)", line)
            if m:
                times_s.append(float(m.group(1)))
    # Convert seconds → minutes; always include 0.0 as a valid anchor
    minutes = sorted({0.0} | {t / 60.0 for t in times_s})
    return minutes


def prune_silence_anchors(anchors: list[float], min_gap: float) -> list[float]:
    """Prunes anchors that are too close to the previous one."""
    pruned: list[float] = []
    for t in anchors:
        if not pruned or t - pruned[-1] >= min_gap:
            pruned.append(t)
    return pruned


def compute_chapter_range(duration_mins: float, anchor_count: int) -> tuple[int, int]:
    """Computes a reasonable min/max chapter range based on talk duration and anchors."""
    target = max(3, min(12, round(duration_mins / 6)))
    max_ch = min(anchor_count, target)
    min_ch = min(3, max_ch)
    return min_ch, max_ch


def snap_to_nearest(
    ts: float, available: list[float], tolerance: float = SNAP_TOLERANCE_MINS
) -> float | None:
    """Snaps a suggested timestamp to the nearest available anchor within tolerance."""
    if not available:
        return None
    nearest = min(available, key=lambda x: abs(x - ts))
    return nearest if abs(nearest - ts) <= tolerance else None


def parse_lm_response(
    response: str,
    available: list[float],
    tolerance: float = SNAP_TOLERANCE_MINS,
) -> list[tuple[float, str]]:
    """Parses LLM output and snaps suggested timestamps to available anchors."""
    chapters: list[tuple[float, str]] = []
    for line in response.strip().splitlines():
        m = re.search(r"\[(\d+(?:\.\d+)?)\]\s+(.+)", line.strip())
        if not m:
            continue
        ts = float(m.group(1))
        name = m.group(2).strip()
        snapped = snap_to_nearest(ts, available, tolerance)
        if snapped is None:
            pr.amber(f"    Dropping chapter '{name}' — timestamp [{ts}] not in anchors")
            continue
        chapters.append((snapped, name))

    if not chapters:
        return []

    # Force first chapter to 0.0 if available
    if 0.0 in available:
        ts0, name0 = chapters[0]
        chapters[0] = (0.0, name0)

    # Deduplicate timestamps (keep first occurrence)
    seen: set[float] = set()
    deduped: list[tuple[float, str]] = []
    for ts, name in chapters:
        if ts not in seen:
            seen.add(ts)
            deduped.append((ts, name))

    # Filter out chapters closer than MIN_CHAPTER_GAP_MINS
    filtered: list[tuple[float, str]] = []
    for ts, name in deduped:
        if not filtered or ts - filtered[-1][0] >= MIN_CHAPTER_GAP_MINS:
            filtered.append((ts, name))
        else:
            pr.amber(
                f"    Dropping '{name}' [{ts:.2f}] — too close to previous chapter"
            )
    return filtered


def generate_chapters(
    transcript_text: str,
    lang: str,
    silence_times: list[float] | None = None,
    duration_mins: float = 0.0,
) -> str:
    """Calls Gemini API to generate chapter suggestions."""
    if silence_times:
        instruction = build_silence_instruction(silence_times, lang, duration_mins)
    else:
        instruction = SYSTEM_INSTRUCTIONS_PARAGRAPHS[lang]
    return generate_with_timeout(
        contents=build_cacheable_contents(transcript_text),
        system_instruction=instruction,
        max_output_tokens=4096,
    )


def already_has_chapters(review_text: str, source_name: str) -> bool:
    """Checks if a review entry already has a chapters block."""
    sections = re.split(r"\n---", review_text)
    for section in sections:
        if f"## Source: {source_name}" in section:
            return "**Chapters:**" in section
    return False


def has_review_entry(review_text: str, source_name: str) -> bool:
    """Checks if a review entry exists for the given source file."""
    return bool(re.search(rf"## Source: {re.escape(source_name)}", review_text))


def insert_chapters_block(
    review_path: Path, source_name: str, chapters: list[tuple[float, str]]
) -> bool:
    """Inserts the chapters block into the review file for the specified source."""
    content = review_path.read_text(encoding="utf-8")
    chapter_lines = "\n".join(f"[{ts:.2f}] {name}" for ts, name in chapters)
    block = f"**Chapters:**\n{chapter_lines}"

    # Insert after **Suggested Tags:** line within this source's section
    pattern = rf"(## Source: {re.escape(source_name)}.*?\*\*Suggested Tags:\*\*[^\n]*)"
    replacement = rf"\1\n{block}"
    new_content, n = re.subn(pattern, replacement, content, count=1, flags=re.DOTALL)
    if n == 0:
        pr.no(f"    Could not locate **Suggested Tags:** for {source_name}")
        return False
    review_path.write_text(new_content, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generates AI chapter timestamps for Dhamma talk transcripts."
    )
    parser.add_argument(
        "--lang",
        type=str,
        required=True,
        choices=["ru", "en"],
        help="Language of the talk (ru|en).",
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder in output/transcribed/ to process. If absent, processes all subfolders.",
    )
    parser.add_argument("--review-file", type=Path, help="Override review file path.")
    parser.add_argument("--file", type=Path, help="Process a single transcript file.")
    parser.add_argument(
        "--test", "-t", action="store_true", help="Use test LLM models."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N transcript files (0=unlimited).",
    )
    args = parser.parse_args()

    from tools.uploader_common import find_latest_review

    transcribed_base = Path("output/transcribed")
    audio_base = Path("audio")

    if not transcribed_base.exists():
        pr.no(f"Base directory not found: {transcribed_base}")
        return

    if not get_working_key():
        pr.no("All API keys failed. Exiting.")
        return

    # Determine folders to process
    if args.folder:
        folders = [transcribed_base / args.folder]
    else:
        folders = [d for d in transcribed_base.iterdir() if d.is_dir()]

    if not folders:
        pr.no("No subfolders found to process.")
        return

    # Phase 1: collect all pending files across all folders
    all_pending: list[tuple[Path, str, Path]] = []
    for folder_path in folders:
        folder_name = folder_path.name
        if args.review_file and args.folder:
            review_path = args.review_file
        else:
            review_path = find_latest_review(f"{folder_name}_review*.md")

        if not review_path or not review_path.exists():
            if args.folder:
                pr.no(f"No review file found for folder '{folder_name}'.")
            continue

        if args.file:
            md_files = [args.file]
        else:
            md_files = sorted(folder_path.rglob("*.md"))

        if not md_files:
            continue

        review_text = review_path.read_text(encoding="utf-8")
        for f in md_files:
            if not has_review_entry(review_text, f.name):
                if args.folder:
                    pr.amber(f"  Skipping {f.name} — no review entry found")
            elif already_has_chapters(review_text, f.name):
                pass
            else:
                all_pending.append((f, folder_name, review_path))

    if args.limit > 0:
        all_pending = all_pending[: args.limit]

    if not all_pending:
        pr.green("Nothing to do.")
        return

    # Phase 2: process
    pr.green_title(f"Generating chapters for {len(all_pending)} files...")
    for i, (file_path, folder_name, review_path) in enumerate(all_pending, 1):
        pr.green(f"  [{i}/{len(all_pending)}] {file_path.name}")
        try:
            transcript = file_path.read_text(encoding="utf-8")
            available = extract_timestamps(transcript)
            if not available:
                pr.no(f"    No timestamps found in {file_path.name}, skipping")
                continue

            duration_mins = max(available) if available else 0.0

            try:
                # Look for audio in audio/{folder_name}/
                audio_path = audio_base / folder_name / (file_path.stem + ".mp3")
                silence_times: list[float] | None = None
                if audio_path.exists():
                    for noise_db in SILENCE_NOISE_DB_LEVELS:
                        detected = detect_silences(audio_path, noise_db=noise_db)
                        pruned = prune_silence_anchors(detected, MIN_CHAPTER_GAP_MINS)
                        if len(pruned) >= MIN_CHAPTERS:
                            silence_times = pruned
                            pr.green(
                                f"    Found {len(detected)} silence anchors → {len(pruned)} after pruning"
                                f" (threshold={noise_db}dB)"
                            )
                            break
                        pr.amber(
                            f"    Only {len(pruned)} pruned silences at {noise_db}dB — trying next threshold"
                        )
                    if silence_times is None:
                        pr.amber("    No sufficient silences found — using paragraphs")
                else:
                    pr.amber(f"    Audio not found: {audio_path} — using paragraphs")

                active_silence_times = silence_times
                pr.bip()
                response = generate_chapters(
                    transcript, args.lang, silence_times, duration_mins
                )
                if not response and silence_times is not None:
                    pr.amber(
                        "    Empty response in silence mode — retrying with paragraphs"
                    )
                    active_silence_times = None
                    response = generate_chapters(
                        transcript, args.lang, None, duration_mins
                    )

                if not response:
                    pr.no("    Empty response from LLM")
                    continue
            except concurrent.futures.TimeoutError:
                pr.amber(f"    Timeout on {file_path.name} — skipping")
                continue

            snap_anchors = active_silence_times if active_silence_times else available
            snap_tol = (
                SILENCE_SNAP_TOLERANCE_MINS
                if active_silence_times
                else SNAP_TOLERANCE_MINS
            )
            chapters = parse_lm_response(response, snap_anchors, tolerance=snap_tol)

            if len(chapters) < MIN_CHAPTERS:
                pr.no(f"    Only {len(chapters)} valid chapters generated — skipping")
                continue

            ok = insert_chapters_block(review_path, file_path.name, chapters)
            if ok:
                pr.yes(f"    {len(chapters)} chapters written")

            if len(all_pending) > 1 and i < len(all_pending):
                time.sleep(3)
        except Exception as e:
            pr.no(f"    Error on {file_path.name}: {e}")

    pr.green("Done.")


if __name__ == "__main__":
    main()
