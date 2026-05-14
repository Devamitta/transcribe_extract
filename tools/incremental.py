#!/usr/bin/env python3
"""Shared utilities for per-chunk incremental LLM result saving and resume."""

import json
from pathlib import Path


def get_temp_path(out_path: Path) -> Path:
    """Returns .{filename}.tmp alongside the output file."""
    return out_path.parent / f".{out_path.name}.tmp"


def load_temp(temp_path: Path) -> list:
    """Load saved chunk results from temp file. Returns [] if missing or corrupt."""
    if not temp_path.exists():
        return []
    try:
        return json.loads(temp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_temp(temp_path: Path, results: list) -> None:
    """Save current chunk results list to temp file as JSON."""
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(json.dumps(results), encoding="utf-8")


def finalize_temp(temp_path: Path) -> None:
    """Delete temp file after successful final write."""
    if temp_path.exists():
        temp_path.unlink()
