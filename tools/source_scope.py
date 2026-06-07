"""Utilities for limiting pipeline stages to sources from the current run."""

import unicodedata
from pathlib import Path


def read_source_filter(source_log: Path | None) -> set[str] | None:
    """Read source names/stems from a log, or return None when no filter was requested."""
    if source_log is None:
        return None
    if not source_log.exists():
        return set()

    allowed: set[str] = set()
    for line in source_log.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        path = Path(raw)
        allowed.add(unicodedata.normalize("NFC", raw))
        allowed.add(unicodedata.normalize("NFC", path.name))
        allowed.add(unicodedata.normalize("NFC", path.stem))
    return allowed


def source_matches_filter(source_name: str, source_filter: set[str] | None) -> bool:
    """Return true when a source name/path is included by the optional source filter."""
    if source_filter is None:
        return True
    path = Path(source_name)
    return (
        unicodedata.normalize("NFC", source_name) in source_filter
        or unicodedata.normalize("NFC", path.name) in source_filter
        or unicodedata.normalize("NFC", path.stem) in source_filter
    )


def path_matches_filter(path: Path, source_filter: set[str] | None) -> bool:
    """Return true when a concrete path is included by the optional source filter."""
    if source_filter is None:
        return True
    return unicodedata.normalize("NFC", str(path)) in source_filter
