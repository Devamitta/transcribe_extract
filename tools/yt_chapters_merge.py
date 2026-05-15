"""Semantic chapter merging for yt_chapters.py using sentence-transformers embeddings."""

from __future__ import annotations

import re

from tools.printer import printer as pr


def get_chapter_text(
    ts: float,
    next_ts: float | None,
    transcript: str,
    available: list[float],
) -> str:
    """Extracts the transcript paragraphs that fall within [ts, next_ts)."""
    lines = []
    for line in transcript.splitlines():
        m = re.match(r"\[(\d+(?:\.\d+)?)\]", line)
        if not m:
            continue
        t = float(m.group(1))
        if t >= ts and (next_ts is None or t < next_ts):
            lines.append(line)
    return " ".join(lines)


def compute_similarity(text_a: str, text_b: str) -> float:
    """Returns cosine similarity between two text segments using multilingual embeddings."""
    from sentence_transformers import SentenceTransformer  # lazy import

    import numpy as np

    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    embs = model.encode([text_a, text_b], convert_to_numpy=True)
    a, b = embs[0], embs[1]
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def merge_close_chapters(
    chapters: list[tuple[float, str]],
    transcript: str,
    available: list[float],
    min_gap: float,
) -> list[tuple[float, str]]:
    """Merges chapters that are too close using semantic similarity.

    The shorter chapter is absorbed into its most-similar neighbour.
    The first chapter (0.0) is never merged away.
    """
    if len(chapters) < 2:
        return chapters

    changed = True
    while changed:
        changed = False
        for i in range(1, len(chapters)):
            ts_prev, name_prev = chapters[i - 1]
            ts_curr, name_curr = chapters[i]
            if ts_curr - ts_prev < min_gap:
                next_ts = chapters[i + 1][0] if i + 1 < len(chapters) else None

                text_curr = get_chapter_text(ts_curr, next_ts, transcript, available)
                text_prev = get_chapter_text(ts_prev, ts_curr, transcript, available)

                sim_to_prev = compute_similarity(text_curr, text_prev)

                if i + 1 < len(chapters):
                    next_next_ts = chapters[i + 2][0] if i + 2 < len(chapters) else None
                    text_next = get_chapter_text(
                        next_ts,  # type: ignore[arg-type]
                        next_next_ts,
                        transcript,
                        available,
                    )
                    sim_to_next = compute_similarity(text_curr, text_next)
                else:
                    sim_to_next = -1.0

                if ts_prev == 0.0:
                    pr.amber(
                        f"    Merging '{name_curr}' [{ts_curr:.2f}] into previous (first chapter protected)"
                    )
                    chapters.pop(i)
                elif sim_to_prev >= sim_to_next:
                    pr.amber(
                        f"    Merging '{name_curr}' [{ts_curr:.2f}] into previous (sim={sim_to_prev:.2f})"
                    )
                    chapters.pop(i)
                else:
                    pr.amber(
                        f"    Merging '{name_prev}' [{ts_prev:.2f}] into next (sim={sim_to_next:.2f})"
                    )
                    chapters.pop(i - 1)

                changed = True
                break

    return chapters
