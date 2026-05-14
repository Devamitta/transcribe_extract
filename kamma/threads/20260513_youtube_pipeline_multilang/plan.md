# Plan: YouTube Pipeline — Continuous Maintenance Thread

## Thread Role
Permanent feedback and correction thread. Completed phases are archived as one-liners below.
New issues are appended under "Current Issue" when reported.

## Architecture Decisions (standing)
- One history file per platform with nested language sections (not flat, not per-language files)
- `--limit` applies globally across all folders (collect all → slice → process)
- Silence detection: try thresholds `-30, -25, -20 dB` in order until MIN_CHAPTERS pruned anchors found
- Chapter range: `target = clamp(round(duration/6), 3, 12)`, capped by anchor count
- Playlist lookup: find-only — exit with error if playlist not found, never create

## Completed Phases (archive)
- Phase 1 (2026-05-13): Thread restructured as feedback loop
- Phase 2 (2026-05-13): Language-scoped upload history for yt + gdrive; Russian history migrated
- Phase 3 (2026-05-13): Docs updated; ruff/pyright clean
- Phase 4 (2026-05-14): `--limit` and `rglob` added to 7 pipeline scripts
- Phase 5 (2026-05-14): `SILENCE_NOISE_DB` changed from -40 to -30
- Phase 6 (2026-05-14): Timestamp precision `:.2f`; `prune_silence_anchors`; `re.search` fix
- Phase 7 (2026-05-14): `compute_chapter_range`; paragraph fallback retry on empty LLM response
- Phase 8 (2026-05-14): `find_existing_playlist` replaces `get_or_create_playlist` in `yt_upload.py`
- Phase 9 (2026-05-14): `yt_update_timestamps.py` created (recordingDate — later corrected)
- Phase 10 (2026-05-14): `yt_update_timestamps.py` rewritten to add missing chapter timestamps to YouTube descriptions

## Current Issue

## Phase 11 — Fix timing (0.000) across pipeline scripts [x]

### Context
`pr.yes()` and `pr.no()` always append elapsed time via `print_bop()`. The timer must be started with `pr.bip()` before each operation. Currently:
- Upload scripts call `pr.white("Uploading...")` — which does NOT call `bip()` — then `pr.yes(...)` via `confirm_and_save_nested`, so `bop()` returns the hardcoded `"0.000"`.
- Other scripts use `pr.yes()` for non-timed status/summary messages instead of `pr.green()`.

### Part A — Add `pr.bip()` before timed operations (5 sites)

- [ ] `scripts/yt_upload.py` line ~252: add `pr.bip()` on the line after `pr.white(f"Uploading: {meta['title']}...")` and before `upload_video()`
  → verify: run with `--dry-run` to confirm no crash; confirm `pr.bip()` line present
- [ ] `scripts/gdrive_upload.py` line ~277: add `pr.bip()` on the line after `pr.white(f"Uploading to Drive: {path.name}...")` and before `upload_file(drive, path, ...)`
  → verify: line present after pr.white
- [ ] `scripts/gdrive_upload.py` line ~302: add `pr.bip()` on the line after `pr.white(f"Uploading audio to Drive: {audio_path.name}...")` and before audio `upload_file(...)`
  → verify: line present after pr.white
- [ ] `scripts/yt_video.py` line ~207: add `pr.bip()` on the line after `pr.amber(f"    Encoding [{folder_name}]: {title}...")` and before `subprocess.run(cmd, ...)`
  → verify: line present after pr.amber
- [ ] `scripts/yt_chapters.py` line ~412: add `pr.bip()` on the line immediately before `response = generate_chapters(...)`
  → verify: line present before generate_chapters call

### Part B — Change non-timed `pr.yes()` → `pr.green()` (14 sites)

- [ ] `scripts/yt_upload.py` line ~195: `pr.yes("Everything already uploaded.")` → `pr.green("Everything already uploaded.")`
- [ ] `scripts/yt_upload.py` line ~301: `pr.yes("Session complete.")` → `pr.green("Session complete.")`
- [ ] `scripts/gdrive_upload.py` line ~203: `pr.yes("Everything already uploaded.")` → `pr.green("Everything already uploaded.")`
- [ ] `scripts/gdrive_upload.py` line ~322: `pr.yes("Session complete.")` → `pr.green("Session complete.")`
- [ ] `scripts/yt_video.py` line ~215: `pr.yes(f"Done: {created} created, ...")` → `pr.green(...)`
- [ ] `scripts/yt_export.py` line ~162: `pr.yes(f"{verb} {len(renamed)} file(s)")` → `pr.green(...)`
- [ ] `scripts/yt_export.py` line ~328: `pr.yes(f"Done: Exported: {exported} | Errors: {errors}")` → `pr.green(...)`
- [ ] `scripts/yt_metadata.py` line ~179: `pr.yes(f"[{folder_name}] All files already processed.")` → `pr.green(...)`
- [ ] `scripts/yt_metadata.py` line ~240: `pr.yes(f"[{folder_name}] Done. Review file: ...")` → `pr.green(...)`
- [ ] `scripts/yt_metadata.py` line ~353: `pr.yes("Nothing to do.")` → `pr.green(...)`
- [ ] `scripts/yt_chapters.py` line ~372: `pr.yes("Nothing to do.")` → `pr.green(...)`
- [ ] `scripts/yt_chapters.py` line ~452: `pr.yes("Done.")` → `pr.green(...)`
- [ ] `scripts/yt_audio_convert.py` line ~124: `pr.yes(f"Converted {total_converted} files")` → `pr.green(...)`
- [ ] `scripts/yt_ingest.py` line ~122: `pr.yes(f"Extracted {total_extracted} audio files")` → `pr.green(...)`

### Part C — Quality checks
- [ ] Run `uv run ruff check --fix` and `uv run ruff format` on all 7 changed files:
  `scripts/yt_upload.py`, `scripts/gdrive_upload.py`, `scripts/yt_video.py`,
  `scripts/yt_chapters.py`, `scripts/yt_export.py`, `scripts/yt_metadata.py`,
  `scripts/yt_audio_convert.py`, `scripts/yt_ingest.py`
  → verify: ruff exits 0
- [ ] Run `uv run python -m pyright` on the same 7 files
  → verify: pyright exits 0

### Note
`tools/uploader_common.py` is NOT changed. Its `confirm_and_save` / `confirm_and_save_nested` functions call `pr.yes()` correctly — the fix is in the callers starting the timer before each upload.

---
<!-- When a new issue arrives, add a Phase block here: -->
<!-- ## Phase N — Title -->
<!-- ### Context -->
<!-- ### Tasks -->
<!-- - [ ] task → verify: ... -->
