"""Generates AI chapter timestamps for Dhamma talk transcripts and appends them to the review file."""

from __future__ import annotations

import argparse
import concurrent.futures
import re
import time
import unicodedata
from pathlib import Path

from tools.printer import printer as pr
from tools.provider import (
    build_cacheable_contents,
    generate_with_timeout,
    get_working_key,
)
from tools.uploader_common import minutes_to_hms
from tools.yt_chapters_merge import merge_close_chapters
from tools.yt_chapters_silence import (
    SILENCE_DEDUP_GAP_MINS,
    SILENCE_MIN_DURATION_S,
    SILENCE_NOISE_DB,
    ContentType,
    build_silence_instruction,
    detect_silences,
    get_audio_duration,
    is_sentence_boundary,
    prune_silence_anchors,
    silence_histogram,
    snap_silences_to_transcript,
)

SNAP_TOLERANCE_MINS = 0.75
SILENCE_SNAP_TOLERANCE_MINS = 0.75
MIN_CHAPTER_GAP_MINS = 2.0
MIN_CHAPTERS = 3

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


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


def extract_timestamps(text: str) -> list[float]:
    """Extracts all [X.X] decimal minute timestamps from the transcript text."""
    return sorted({float(m) for m in re.findall(r"\[(\d+(?:\.\d+)?)\]", text)})


def extract_paragraphs(text: str) -> list[tuple[float, str]]:
    """Returns (timestamp_min, paragraph_text) pairs sorted by timestamp."""
    out: list[tuple[float, str]] = []
    for line in text.splitlines():
        m = re.match(r"\[(\d+(?:\.\d+)?)\]\s+(.*)", line)
        if m:
            out.append((float(m.group(1)), m.group(2).strip()))
    return sorted(out, key=lambda x: x[0])


def check_transcript_density(
    paragraphs: list[tuple[float, str]], max_median_gap_mins: float = 0.6
) -> tuple[bool, float]:
    """Returns (is_dense, median_gap).

    A median gap > 0.6 min (36s) means the transcript was chunked too coarsely — chapters would
    snap to large intervals instead of the ~30s granularity needed for accurate placement.
    Re-transcribe with --chunk-seconds 20 to fix.
    """
    if len(paragraphs) < 3:
        return True, 0.0
    gaps = sorted(
        [paragraphs[i + 1][0] - paragraphs[i][0] for i in range(len(paragraphs) - 1)]
    )
    median_gap = gaps[len(gaps) // 2]
    return (median_gap <= max_median_gap_mins, median_gap)


def classify_content(
    transcript: str, folder_name: str, duration_mins: float
) -> ContentType:
    """Classifies transcript as 'talk' or 'qa' using WPM, punctuation density, and folder hint."""
    words = transcript.split()
    word_count = len(words)
    wpm = word_count / duration_mins if duration_mins > 0 else 0.0
    qmarks = transcript.count("?")
    qpm = qmarks / duration_mins if duration_mins > 0 else 0.0

    folder_hint_qa = folder_name.lower() == "interview"

    if folder_hint_qa and wpm > 110:
        return "qa"
    if wpm > 140 and qpm > 0.8:
        return "qa"
    return "talk"


def validate_chapters(
    chapters: list[tuple[float, str]],
    min_gap: float,
    duration_mins: float,
    min_count: int = MIN_CHAPTERS,
) -> bool:
    """Validates chapters meet YouTube platform requirements. Logs and returns False on failure."""
    if not chapters:
        pr.no("    Validation failed: chapter list is empty")
        return False
    if chapters[0][0] != 0.0:
        pr.no(
            f"    Validation failed: first chapter timestamp is {chapters[0][0]:.2f}, expected 0.0"
        )
        return False
    if len(chapters) < min_count:
        pr.no(
            f"    Validation failed: only {len(chapters)} chapters (minimum {min_count})"
        )
        return False

    # YouTube policy: chapters must be at least 10s apart, including end of video
    YT_MIN_GAP_MINS = 10.0 / 60.0

    if duration_mins > 0 and (duration_mins - chapters[-1][0] < YT_MIN_GAP_MINS):
        pr.no(
            f"    Validation failed: last chapter is too close to end ({duration_mins - chapters[-1][0]:.2f} min < {YT_MIN_GAP_MINS:.2f})"
        )
        return False

    for i in range(1, len(chapters)):
        if chapters[i][0] <= chapters[i - 1][0]:
            pr.no(
                f"    Validation failed: timestamps not strictly ascending at index {i} ({chapters[i - 1][0]:.2f} → {chapters[i][0]:.2f})"
            )
            return False
        gap = chapters[i][0] - chapters[i - 1][0]
        if gap < YT_MIN_GAP_MINS:
            pr.no(
                f"    Validation failed: chapters {i - 1} and {i} are too close ({gap:.2f} min)"
            )
            return False
        if gap < min_gap:
            # This is our internal quality preference, not a hard platform failure usually,
            # but we treat it as a failure for consistency with merge logic.
            pr.no(
                f"    Validation failed: chapters {i - 1} and {i} are {gap:.2f} min apart (min {min_gap})"
            )
            return False
    return True


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

    return deduped


def generate_chapters(
    transcript: str,
    lang: str,
    silence_pairs: list[tuple[float, float]] | None,
    duration_mins: float = 0.0,
    content_type: ContentType = "talk",
    paragraphs: list[tuple[float, str]] | None = None,
) -> str | None:
    """Calls Gemini API to generate chapters from transcript."""
    if silence_pairs is not None:
        instruction = build_silence_instruction(
            silence_pairs, lang, duration_mins, content_type, paragraphs=paragraphs
        )

    else:
        instruction = SYSTEM_INSTRUCTIONS_PARAGRAPHS[lang]
    return generate_with_timeout(
        contents=build_cacheable_contents(transcript),
        system_instruction=instruction,
        max_output_tokens=4096,
    )


def already_has_chapters(review_text: str, source_name: str) -> bool:
    """Checks if a review entry already has a timed chapters block."""
    sections = re.split(r"\n---", review_text)
    for section in sections:
        if f"## Source: {source_name}" in section:
            if "**Chapters:**" not in section:
                return False
            # Only counts as "has chapters" if at least one line has a timestamp
            m = re.search(
                r"\*\*Chapters:\*\*\n(.*?)(?=\n\*\*|\n##|\Z)", section, re.DOTALL
            )
            if not m:
                return False
            return bool(re.search(r"^\[[\d:]+\]", m.group(1), re.MULTILINE))
    return False


def has_untimed_chapters(review_text: str, source_name: str) -> bool:
    """Checks if a review entry has a chapters block with names but no timestamps."""
    sections = re.split(r"\n---", review_text)
    for section in sections:
        if f"## Source: {source_name}" in section:
            if "**Chapters:**" not in section:
                return False
            m = re.search(
                r"\*\*Chapters:\*\*\n(.*?)(?=\n\*\*|\n##|\Z)", section, re.DOTALL
            )
            if not m:
                return False
            block = m.group(1).strip()
            if not block:
                return False
            # Has content but no [HH:MM:SS] timestamps → untimed
            return not bool(re.search(r"^\[[\d:]+\]", block, re.MULTILINE))
    return False


def parse_untimed_chapter_names(review_text: str, source_name: str) -> list[str]:
    """Returns the list of untimed chapter names from the review entry."""
    sections = re.split(r"\n---", review_text)
    for section in sections:
        if f"## Source: {source_name}" in section:
            m = re.search(
                r"\*\*Chapters:\*\*\n(.*?)(?=\n\*\*|\n##|\Z)", section, re.DOTALL
            )
            if m:
                return [
                    line.strip() for line in m.group(1).splitlines() if line.strip()
                ]
    return []


def has_review_entry(review_text: str, source_name: str) -> bool:
    """Checks if a review entry exists for the given source file."""
    return bool(re.search(rf"## Source: {re.escape(source_name)}", review_text))


def insert_chapters_block(
    review_path: Path, source_name: str, chapters: list[tuple[float, str]]
) -> bool:
    """Inserts the chapters block into the review file for the specified source."""
    from tools.uploader_common import minutes_to_hms

    content = review_path.read_text(encoding="utf-8")
    chapter_lines = "\n".join(f"[{minutes_to_hms(ts)}] {name}" for ts, name in chapters)
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


def replace_untimed_chapters_block(
    review_path: Path, source_name: str, chapters: list[tuple[float, str]]
) -> bool:
    """Replaces an untimed **Chapters:** block with timestamped chapters."""
    from tools.uploader_common import minutes_to_hms

    content = review_path.read_text(encoding="utf-8")
    chapter_lines = "\n".join(f"[{minutes_to_hms(ts)}] {name}" for ts, name in chapters)
    timed_block = f"**Chapters:**\n{chapter_lines}"

    # Replace the existing untimed block (names without [HH:MM:SS] prefix)
    pattern = r"(\*\*Chapters:\*\*\n)((?:(?!\[[\d:]+\])(?!\*\*).+\n?)*)"

    def _in_source_section(text: str) -> bool:
        # Verify the match is within the correct source section
        return f"## Source: {source_name}" in text

    # Scope replacement to the correct source section by splitting on ---
    sections = content.split("\n---")
    replaced = False
    for idx, section in enumerate(sections):
        if f"## Source: {source_name}" in section:
            new_section, n = re.subn(pattern, timed_block + "\n", section, count=1)
            if n > 0:
                sections[idx] = new_section
                replaced = True
                break

    if not replaced:
        pr.no(f"    Could not locate untimed **Chapters:** block for {source_name}")
        return False

    review_path.write_text("\n---".join(sections), encoding="utf-8")
    return True


def build_timestamp_finding_instruction(chapter_names: list[str], lang: str) -> str:
    """Builds a system instruction for finding timestamps for pre-defined chapter names."""
    names_block = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(chapter_names))
    if lang == "ru":
        return f"""You are given a list of chapter names and a timestamped transcript of a Russian Buddhist Dhamma talk.

Your task: assign each chapter name to the exact transcript timestamp where that topic begins.

Chapter names (in order):
{names_block}

Transcript format:
[X.X] paragraph text...

X.X is the paragraph start time in MINUTES (decimal). These are the ONLY valid timestamps.

Rules:
- Output exactly one line per chapter, in the same order as the input list
- The FIRST chapter MUST use timestamp [0.0]
- Copy timestamps EXACTLY as they appear in the transcript — do NOT invent new ones
- Each chapter must span at least 2 minutes of content

Output format — one chapter per line, nothing else, no explanations, no markdown:
[0.0] {chapter_names[0] if chapter_names else "Название первой главы"}
[X.X] {chapter_names[1] if len(chapter_names) > 1 else "Название следующей главы"}
"""
    return f"""You are given a list of chapter names and a timestamped transcript of an English Buddhist Dhamma talk.

Your task: assign each chapter name to the exact transcript timestamp where that topic begins.

Chapter names (in order):
{names_block}

Transcript format:
[X.X] paragraph text...

X.X is the paragraph start time in MINUTES (decimal). These are the ONLY valid timestamps.

Rules:
- Output exactly one line per chapter, in the same order as the input list
- The FIRST chapter MUST use timestamp [0.0]
- Copy timestamps EXACTLY as they appear in the transcript — do NOT invent new ones
- Each chapter must span at least 2 minutes of content

Output format — one chapter per line, nothing else, no explanations, no markdown:
[0.0] {chapter_names[0] if chapter_names else "Name of the first chapter"}
[X.X] {chapter_names[1] if len(chapter_names) > 1 else "Name of the next chapter"}
"""


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
        help="Subfolder in output/transcribed/ to process. Defaults to lang-based folder (ru→russian, en→english).",
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
    parser.add_argument(
        "--silence-min-dur",
        type=float,
        default=SILENCE_MIN_DURATION_S,
        help=f"Minimum silence duration in seconds to count as a topic-break candidate (default: {SILENCE_MIN_DURATION_S})",
    )
    parser.add_argument(
        "--snap-tolerance",
        type=float,
        default=SILENCE_SNAP_TOLERANCE_MINS,
        help=f"Tolerance in minutes for snapping LLM timestamps to anchors (default: {SILENCE_SNAP_TOLERANCE_MINS})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print verbose diagnostics at every filter stage.",
    )
    parser.add_argument(
        "--silence-noise-db",
        type=int,
        default=SILENCE_NOISE_DB,
        help=f"Noise floor (dB) below which audio counts as silent (default: {SILENCE_NOISE_DB})",
    )
    parser.add_argument(
        "--diagnose-only",
        action="store_true",
        help="Run silence detection and diagnostics but skip LLM call and chapter write.",
    )
    parser.add_argument(
        "--debug-log",
        action="store_true",
        help="Write the full --debug trace to temp/yt_chapters_debug_<stem>.log per file",
    )
    parser.add_argument(
        "--silence-mode",
        action="store_true",
        help="Use ffmpeg silence detection to constrain chapter anchors (experimental). Default: paragraph mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be processed; skip API calls and review edits.",
    )
    args = parser.parse_args()

    debug_buffer: list[str] = []

    def dbg(msg: str) -> None:
        line = f"    [debug] {msg}"
        if args.debug:
            pr.amber(line)
        if args.debug_log:
            debug_buffer.append(line)

    def _flush_debug_log(file_path: Path, buf: list[str]) -> None:
        Path("temp").mkdir(exist_ok=True)
        log_path = Path("temp") / f"yt_chapters_debug_{file_path.stem}.log"
        log_path.write_text("\n".join(buf), encoding="utf-8")
        buf.clear()

    transcribed_base = Path("output/transcribed")
    audio_base = Path("output/audio")

    if not transcribed_base.exists():
        pr.no(f"Base directory not found: {transcribed_base}")
        return

    if not args.dry_run and not get_working_key():
        pr.no("All API keys failed. Exiting.")
        return

    # Determine folders to process
    if args.folder is not None:
        folders = [transcribed_base / args.folder]
    else:
        folders = [transcribed_base / LANG_TO_FOLDER[args.lang]]

    if not folders:
        pr.no("No subfolders found to process.")
        return

    # Phase 1: collect all pending files across all folders
    # tuple: (file_path, folder_name, review_path, untimed_mode)
    all_pending: list[tuple[Path, str, Path, bool]] = []
    lang_folder = LANG_TO_FOLDER.get(args.lang, "english")
    for folder_path in folders:
        folder_name = args.folder if args.folder is not None else folder_path.name
        review_path = args.review_file or Path("reviews") / f"{lang_folder}_review.md"

        if not review_path or not review_path.exists():
            if args.folder:
                pr.no(f"No review file found at '{review_path}'.")
            continue

        if args.file:
            md_files = [args.file]
        else:
            md_files = sorted(folder_path.glob("*.md"))

        if not md_files:
            continue

        review_text = review_path.read_text(encoding="utf-8")
        for f in md_files:
            nfc_name = unicodedata.normalize("NFC", f.name)
            if not has_review_entry(review_text, nfc_name):
                if args.folder:
                    pr.amber(f"  Skipping {f.name} — no review entry found")
            elif already_has_chapters(review_text, nfc_name):
                pass
            elif has_untimed_chapters(review_text, nfc_name):
                all_pending.append((f, folder_name, review_path, True))
            else:
                all_pending.append((f, folder_name, review_path, False))

    if args.limit > 0:
        all_pending = all_pending[: args.limit]

    if not all_pending:
        pr.green("Nothing to do.")
        return

    if args.dry_run:
        lang_folder = LANG_TO_FOLDER.get(args.lang, "english")
        review_file = Path("reviews") / f"{lang_folder}_review.md"
        _scan_folder = args.folder if args.folder is not None else lang_folder
        input_dir = transcribed_base / _scan_folder
        pr.green(f"[DRY RUN] Input:  {input_dir}/")
        pr.green(f"[DRY RUN] Output: {review_file} (chapters block)")
        for file_path, _folder, _review, _untimed in all_pending:
            pr.white(f"  {file_path} → {review_file}")
        return

    # Phase 2: process
    pr.green_title(f"Generating chapters for {len(all_pending)} files...")
    for i, (file_path, folder_name, review_path, untimed_mode) in enumerate(
        all_pending, 1
    ):
        mode_label = "timing" if untimed_mode else "generate"
        pr.green(f"  [{i}/{len(all_pending)}] {file_path.name} ({mode_label})")
        nfc_name = unicodedata.normalize("NFC", file_path.name)
        try:
            transcript = file_path.read_text(encoding="utf-8")
            available = extract_timestamps(transcript)
            if not available:
                pr.no(f"    No timestamps found in {file_path.name}, skipping")
                continue

            paragraphs = extract_paragraphs(transcript)
            is_dense, median_gap = check_transcript_density(paragraphs)
            if not is_dense:
                pr.no(
                    f"    Transcript too sparse (median gap {median_gap:.2f} min = {median_gap * 60:.0f}s, "
                    "threshold 36s)"
                )
                continue

            duration_mins = max(available) if available else 0.0

            if duration_mins < 3.0:
                pr.no(f"    Transcript too short ({duration_mins:.1f} min < 3.0 min)")
                continue

            content_type = classify_content(transcript, folder_name, duration_mins)
            pr.green(f"    Content type: {content_type}")

            active_min_gap = 1.0 if content_type == "qa" else MIN_CHAPTER_GAP_MINS

            # --- Untimed mode: user pre-filled chapter names, find timestamps ---
            if untimed_mode:
                review_text = review_path.read_text(encoding="utf-8")
                chapter_names = parse_untimed_chapter_names(review_text, nfc_name)
                if not chapter_names:
                    pr.no(f"    No chapter names found for {file_path.name}, skipping")
                    continue
                pr.green(
                    f"    Finding timestamps for {len(chapter_names)} pre-defined chapters"
                )
                instruction = build_timestamp_finding_instruction(
                    chapter_names, args.lang
                )
                pr.bip()
                try:
                    response = generate_with_timeout(
                        contents=build_cacheable_contents(transcript),
                        system_instruction=instruction,
                        max_output_tokens=2048,
                    )
                except concurrent.futures.TimeoutError:
                    pr.amber(f"    Timeout on {file_path.name} — skipping")
                    if args.debug_log and debug_buffer:
                        _flush_debug_log(file_path, debug_buffer)
                    continue

                if not response:
                    pr.no("    Empty response from LLM")
                    if args.debug_log and debug_buffer:
                        _flush_debug_log(file_path, debug_buffer)
                    continue

                dbg(f"LLM raw response: {response[:500]!r}")
                chapters = parse_lm_response(
                    response, available, tolerance=args.snap_tolerance
                )
                dbg(f"parsed chapters: {[(ts, n) for ts, n in chapters]}")

                if len(chapters) < MIN_CHAPTERS:
                    pr.no(f"    Only {len(chapters)} valid chapters — skipping")
                    continue

                if duration_mins > 0 and (
                    duration_mins - chapters[-1][0] < (10.0 / 60.0)
                ):
                    pr.amber(
                        f"    Dropping last chapter '{chapters[-1][1]}' — too close to end"
                    )
                    chapters.pop()

                if not validate_chapters(chapters, active_min_gap, duration_mins):
                    pr.no(
                        f"    Chapter validation failed for {file_path.name} — skipping write"
                    )
                    continue

                ok = replace_untimed_chapters_block(review_path, nfc_name, chapters)
                if ok:
                    pr.yes(
                        f"    {len(chapters)} chapters timed ({minutes_to_hms(duration_mins)})"
                    )

                if args.debug_log and debug_buffer:
                    _flush_debug_log(file_path, debug_buffer)
                if len(all_pending) > 1 and i < len(all_pending):
                    time.sleep(3)
                continue

            # --- Normal mode: generate chapters from scratch ---
            try:
                # Look for audio in audio/{folder_name}/
                audio_path = audio_base / folder_name / (file_path.stem + ".mp3")
                silence_pairs: list[tuple[float, float]] | None = None
                if args.silence_mode and audio_path.exists():
                    duration_mins = get_audio_duration(audio_path)
                    raw_pairs = detect_silences(
                        audio_path,
                        noise_db=args.silence_noise_db,
                        min_dur_s=args.silence_min_dur,
                    )
                    dbg(
                        f"raw silences: {len(raw_pairs)} (min_dur={args.silence_min_dur}s)"
                    )

                    # Diagnostic pass: histogram of all silences >= 2s
                    if args.debug:
                        diag_pairs = detect_silences(
                            audio_path, noise_db=args.silence_noise_db, min_dur_s=2.0
                        )
                        dbg(f"all silences ≥2s: {len(diag_pairs)}")
                        dbg(f"histogram: {silence_histogram(diag_pairs)}")
                        for s_mid_min, s_dur in diag_pairs:
                            dbg(f"  silence @ [{s_mid_min:.2f}min] dur={s_dur:.2f}s")

                    # Light dedup: collapse near-duplicate midpoints (< 0.3 min apart)
                    raw_midpoints = [m for m, _ in raw_pairs]
                    deduped_midpoints = prune_silence_anchors(
                        raw_midpoints, SILENCE_DEDUP_GAP_MINS
                    )
                    dbg(f"after dedup: {len(deduped_midpoints)}")

                    # Snap each silence midpoint to the nearest transcript paragraph
                    snapped_times = snap_silences_to_transcript(
                        deduped_midpoints, available
                    )
                    dbg(f"snapped to transcript: {len(snapped_times)}")

                    snap_pre_filter = len(snapped_times)

                    filtered_times: list[float] = []
                    for t in snapped_times:
                        if t == 0.0:
                            filtered_times.append(t)
                            continue
                        idx = next(
                            (j for j, (ts, _) in enumerate(paragraphs) if ts == t),
                            None,
                        )
                        if idx is None or idx == 0:
                            filtered_times.append(t)
                            continue
                        prev_txt = paragraphs[idx - 1][1]
                        curr_txt = paragraphs[idx][1]
                        ok, reason = is_sentence_boundary(prev_txt, curr_txt)
                        if ok:
                            filtered_times.append(t)
                        else:
                            if args.debug:
                                pr.amber(f"    Dropping anchor [{t:.2f}] — {reason}")
                    snapped_times = filtered_times
                    dbg(f"after sentence-boundary filter: {len(snapped_times)}")
                    dbg(
                        f"stage summary: raw={len(raw_pairs)} → dedup={len(deduped_midpoints)} "
                        f"→ snap={snap_pre_filter} → post-sentence={len(snapped_times)}"
                    )

                    def nearest_dur(
                        t: float, pairs: list[tuple[float, float]]
                    ) -> float:
                        return min(pairs, key=lambda x: abs(x[0] - t))[1]

                    silence_pairs = [
                        (t, nearest_dur(t, raw_pairs)) for t in snapped_times
                    ]

                    pr.green(
                        f"    Found {len(silence_pairs)} transcript-snapped anchors"
                    )
                    if len(silence_pairs) < MIN_CHAPTERS:
                        pr.amber("    Insufficient silence anchors — using paragraphs")
                        silence_pairs = None
                elif args.silence_mode:
                    pr.amber(f"    Audio not found: {audio_path} — using paragraphs")

                if args.diagnose_only:
                    pr.amber("    --diagnose-only: skipping LLM call")
                    if args.debug_log and debug_buffer:
                        _flush_debug_log(file_path, debug_buffer)
                    continue

                active_silence_times = (
                    [m for m, _ in silence_pairs] if silence_pairs else None
                )
                dbg(f"final anchors → LLM: {active_silence_times}")
                pr.bip()
                response = generate_chapters(
                    transcript,
                    args.lang,
                    silence_pairs,
                    duration_mins,
                    content_type,
                    paragraphs=paragraphs,
                )
                if not response and silence_pairs is not None:
                    pr.amber(
                        "    Empty response in silence mode — retrying with paragraphs"
                    )
                    active_silence_times = None
                    response = generate_chapters(
                        transcript,
                        args.lang,
                        None,
                        duration_mins,
                        content_type,
                        paragraphs=paragraphs,
                    )

                if not response:
                    pr.no("    Empty response from LLM")
                    if args.debug_log and debug_buffer:
                        _flush_debug_log(file_path, debug_buffer)
                    continue
                dbg(f"LLM raw response: {response[:500]!r}")
            except concurrent.futures.TimeoutError:
                pr.amber(f"    Timeout on {file_path.name} — skipping")
                if args.debug_log and debug_buffer:
                    _flush_debug_log(file_path, debug_buffer)
                continue

            snap_anchors = active_silence_times if active_silence_times else available
            snap_tol = args.snap_tolerance
            chapters = parse_lm_response(response, snap_anchors, tolerance=snap_tol)
            dbg(f"parsed chapters: {[(ts, n) for ts, n in chapters]}")
            chapters = merge_close_chapters(
                chapters, transcript, snap_anchors, active_min_gap
            )
            dbg(f"after merge: {[(ts, n) for ts, n in chapters]}")

            if len(chapters) < MIN_CHAPTERS:
                pr.no(f"    Only {len(chapters)} valid chapters generated — skipping")
                continue

            # Final safety: if last chapter is too close to end, drop it
            if duration_mins > 0 and (duration_mins - chapters[-1][0] < (10.0 / 60.0)):
                pr.amber(
                    f"    Dropping last chapter '{chapters[-1][1]}' — too close to end"
                )
                chapters.pop()

            if not validate_chapters(chapters, active_min_gap, duration_mins):
                pr.no(
                    f"    Chapter validation failed for {file_path.name} — skipping write"
                )
                continue

            ok = insert_chapters_block(review_path, nfc_name, chapters)
            if ok:
                pr.yes(
                    f"    {len(chapters)} chapters written ({minutes_to_hms(duration_mins)})"
                )

            if args.debug_log and debug_buffer:
                _flush_debug_log(file_path, debug_buffer)

            if len(all_pending) > 1 and i < len(all_pending):
                time.sleep(3)
        except Exception as e:
            pr.no(f"    Error on {file_path.name}: {e}")
            if args.debug_log and debug_buffer:
                _flush_debug_log(file_path, debug_buffer)

    pr.green("Done.")


if __name__ == "__main__":
    main()
