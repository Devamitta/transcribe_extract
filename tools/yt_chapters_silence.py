"""Silence-detection helpers for yt_chapters.py chapter generation (--silence-mode)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Literal


ContentType = Literal["talk", "qa"]

SILENCE_NOISE_DB = -20
SILENCE_MIN_DURATION_S = 3.0
SILENCE_DEDUP_GAP_MINS = 0.3
SILENCE_TO_TRANSCRIPT_TOLERANCE_MINS = 1.5

SILENCE_BUCKETS_S = [
    (2.0, 3.0),
    (3.0, 4.0),
    (4.0, 5.0),
    (5.0, 6.0),
    (6.0, 8.0),
    (8.0, 999.0),
]

SENTENCE_TERMINAL_CHARS = (".", "!", "?", "…", ":", "»", '"', ")")


def compute_chapter_range(duration_mins: float, anchor_count: int) -> tuple[int, int]:
    """Computes a reasonable min/max chapter range based on talk duration and anchors."""
    target = round(duration_mins / 6)
    if duration_mins >= 60:
        target = max(target, 8)
    elif duration_mins >= 30:
        target = max(target, 6)
    elif duration_mins >= 20:
        target = max(target, 4)
    target = max(3, min(15, target))
    max_ch = min(anchor_count, target)
    min_ch = min(3, max_ch)
    return min_ch, max_ch


def get_audio_duration(audio_path: Path) -> float:
    """Returns audio duration in minutes using ffprobe."""
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip()) / 60.0
    except (ValueError, subprocess.CalledProcessError):
        return 0.0


def detect_silences(
    audio_path: Path,
    noise_db: int = SILENCE_NOISE_DB,
    min_dur_s: float = SILENCE_MIN_DURATION_S,
) -> list[tuple[float, float]]:
    """Return (midpoint_minutes, duration_seconds) pairs for each detected silence."""
    cmd = [
        "ffmpeg",
        "-i",
        str(audio_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_dur_s}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    output = result.stderr

    midpoints: list[tuple[float, float]] = [(0.0, 0.0)]
    current_start: float | None = None
    for line in output.splitlines():
        if "silence_start:" in line:
            m = re.search(r"silence_start:\s*([\d.]+)", line)
            if m:
                current_start = float(m.group(1))
        elif "silence_end:" in line and current_start is not None:
            m = re.search(r"silence_end:\s*([\d.]+)", line)
            if m:
                end_s = float(m.group(1))
                mid_s = (current_start + end_s) / 2.0
                dur_s = end_s - current_start
                midpoints.append((mid_s / 60.0, dur_s))
                current_start = None
    return sorted(midpoints, key=lambda x: x[0])


def prune_silence_anchors(anchors: list[float], min_gap: float) -> list[float]:
    """Prunes anchors that are too close to the previous one."""
    pruned: list[float] = []
    for t in anchors:
        if not pruned or t - pruned[-1] >= min_gap:
            pruned.append(t)
    return pruned


def snap_silences_to_transcript(
    silence_midpoints: list[float], transcript_times: list[float]
) -> list[float]:
    """Maps each silence midpoint to the nearest transcript timestamp within tolerance. Always includes 0.0."""
    snapped: set[float] = {0.0}
    for sm in silence_midpoints:
        if not transcript_times:
            continue
        nearest = min(transcript_times, key=lambda x: abs(x - sm))
        if abs(nearest - sm) <= SILENCE_TO_TRANSCRIPT_TOLERANCE_MINS:
            snapped.add(nearest)
    return sorted(list(snapped))


def silence_histogram(raw_pairs: list[tuple[float, float]]) -> str:
    """Returns a one-line histogram of silence durations."""
    counts = [0] * len(SILENCE_BUCKETS_S)
    for _, dur_s in raw_pairs:
        for i, (lo, hi) in enumerate(SILENCE_BUCKETS_S):
            if lo <= dur_s < hi:
                counts[i] += 1
                break
    parts = [
        f"[{lo:.0f}–{hi:.0f}s]:{c}" for (lo, hi), c in zip(SILENCE_BUCKETS_S, counts)
    ]
    return " ".join(parts)


def is_sentence_boundary(prev_text: str, curr_text: str) -> tuple[bool, str]:
    """Returns (is_boundary, reason). True if the gap between prev_text and curr_text
    looks like a real sentence/topic break."""
    prev_clean = prev_text.rstrip()
    curr_clean = curr_text.lstrip()
    if not prev_clean:
        return True, "no previous text (talk start)"
    if not prev_clean.endswith(SENTENCE_TERMINAL_CHARS):
        return False, f"prev does not end with terminal punct: ...{prev_clean[-30:]!r}"
    if not curr_clean:
        return False, "curr text is empty"
    first = curr_clean[0]
    if not (first.isupper() or first.isdigit() or first in "—«\"'("):
        return False, f"curr starts non-capital: {curr_clean[:30]!r}"
    return True, "ok"


def build_silence_instruction(
    silence_pairs: list[tuple[float, float]],
    lang: str,
    duration_mins: float = 0.0,
    content_type: ContentType = "talk",
    paragraphs: list[tuple[float, str]] | None = None,
) -> str:
    """Build system instruction that pins the LLM to real silence break points with durations."""
    min_ch, max_ch = compute_chapter_range(duration_mins, len(silence_pairs))

    if paragraphs:
        sorted_paras = sorted(paragraphs, key=lambda x: x[0])
        idx_by_ts = {ts: i for i, (ts, _) in enumerate(sorted_paras)}
        lines = []
        for m, d in silence_pairs:
            i = idx_by_ts.get(m)
            prev_tail = sorted_paras[i - 1][1][-80:] if i and i > 0 else ""
            curr_head = sorted_paras[i][1][:80] if i is not None else ""
            lines.append(
                f"[{m:.2f}] (silence {d:.1f}s)\n"
                f"  ends: ...{prev_tail!r}\n"
                f"  starts: {curr_head!r}..."
            )
        ts_list = "\n".join(lines)
    else:
        ts_list = "  ".join(f"[{m:.2f}] ({d:.1f}s)" for m, d in silence_pairs)

    qa_note = (
        "\n- This is a Q&A session: chapters may be as short as 1 minute; mark each distinct question topic"
        if content_type == "qa"
        else ""
    )

    if lang == "ru":
        return f"""You are analyzing a Russian Buddhist Dhamma talk.

The following timestamps mark transcript paragraph start times, selected because they
follow an audio silence — they mark likely topic transitions.
Each entry shows the timestamp and the silence duration that preceded it — longer
pauses are stronger signals of topic transitions. These are your only valid timestamps.
{ts_list}

The transcript below is for content understanding only.

Step 1 — Read the transcript and identify where topics meaningfully change.
Step 2 — For each transition, pick the nearest timestamp from the list above.
         Prefer longer silences when two candidates are close to a transition.
         Reject any anchor where the 'ends:' snippet does not finish a sentence — these are word-finding pauses, not topic transitions.

Rules:
- The FIRST chapter MUST be [0.00] — always in the list above
- Use ONLY timestamps from the list — no other values
- Chapter names: Russian, 2–5 words, descriptive of the actual content
- Aim for {min_ch}–{max_ch} chapters; use fewer if the talk has fewer true transitions
- Each chapter must span at least 2–3 minutes{qa_note}

Output format — one chapter per line, nothing else, no explanations, no markdown:
[0.00] Название первой главы
[X.XX] Название следующей главы
"""
    else:
        return f"""You are analyzing an English Buddhist Dhamma talk.

The following timestamps mark transcript paragraph start times, selected because they
follow an audio silence — they mark likely topic transitions.
Each entry shows the timestamp and the silence duration that preceded it — longer
pauses are stronger signals of topic transitions. These are your only valid timestamps.
{ts_list}

The transcript below is for content understanding only.

Step 1 — Read the transcript and identify where topics meaningfully change.
Step 2 — For each transition, pick the nearest timestamp from the list above.
         Prefer longer silences when two candidates are close to a transition.
         Reject any anchor where the 'ends:' snippet does not finish a sentence — these are word-finding pauses, not topic transitions.

Rules:
- The FIRST chapter MUST be [0.00] — always in the list above
- Use ONLY timestamps from the list — no other values
- Chapter names: English, 2–5 words, descriptive of the actual content
- Aim for {min_ch}–{max_ch} chapters; use fewer if the talk has fewer true transitions
- Each chapter must span at least 2–3 minutes{qa_note}

Output format — one chapter per line, nothing else, no explanations, no markdown:
[0.00] Name of the first chapter
[X.XX] Name of the next chapter
"""
