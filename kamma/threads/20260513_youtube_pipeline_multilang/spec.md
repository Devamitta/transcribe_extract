# Spec: YouTube Pipeline — Continuous Maintenance Thread

## Status
Active. This is the permanent maintenance thread for the multilingual YouTube pipeline.
Do not create a new thread for minor issues — append them here instead.

## Purpose
Track each user-reported pipeline issue as a correction cycle:
report → plan → implement → summarize → repeat.

## Scope
- All `yt_*.py` scripts and `gdrive_upload.py`
- Upload history files: `output/youtube_history.json`, `output/gdrive_history.json`
- Thread files remain summary-only after each cycle; no exhaustive task detail in archive

## Operating Model
1. User reports issue → agent appends it under "Next Issue" in `plan.md`
2. Agent records context in `spec.md`, `plan.md`, `handoff.md`
3. New session implements the planned correction
4. Agent appends one-line summary to fix history in `handoff.md`
5. Thread files are compressed again if they grow heavy

## Constraints
- Python: type hints, `Path`, `printer.py`, ruff + pyright required
- One commit per fix cycle
- Large or independent issues get their own thread; everything else stays here
