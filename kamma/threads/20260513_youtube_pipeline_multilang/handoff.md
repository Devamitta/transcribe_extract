# Handoff: YouTube Pipeline — Continuous Maintenance Thread

## Status
Phase 11 complete (2026-05-14). Ready for review.

## Confirmed Thread Workflow
1. User runs the pipeline and reports a concrete issue.
2. Agent records the issue in `spec.md`, `plan.md`, `handoff.md`.
3. New session implements the correction.
4. Agent appends a one-line entry to Completed Fix History below.
5. Thread files are compressed again if they grow heavy.

## Key Files
- History: `output/youtube_history.json` (nested `ru`/`en`), `output/gdrive_history.json` (nested `ru.video`, `ru.audio`, `en.video`, `en.audio`)
- One-time chapter patcher: `scripts/yt_update_timestamps.py` (requires `youtube_token_{lang}_edit.json`, `youtube.force-ssl` scope)

## Completed Fix History
- **2026-05-13** — Chapter spacing enforced (`MIN_CHAPTER_GAP_MINS = 2.0`); duplicate chapter detection fixed; duplicate blocks cleaned from `reviews/russian_review.md`
- **2026-05-13** — Language-scoped upload history: `load_nested_history` / `save_nested_history` in `tools/uploader_common.py`; Russian history auto-migrated; docs updated
- **2026-05-14** — `--limit` (global collect-then-slice) and `rglob` added to 7 `yt_*.py` scripts
- **2026-05-14** — `SILENCE_NOISE_DB` -40 → -30; later replaced with adaptive multi-level threshold `[-30, -25, -20]`
- **2026-05-14** — Timestamp precision `:.1f` → `:.2f`; `prune_silence_anchors` added; `re.match` → `re.search` in `parse_lm_response`
- **2026-05-14** — `compute_chapter_range` (duration-based, capped by anchors); paragraph fallback retry on empty LLM response
- **2026-05-14** — `max_output_tokens` 1024 → 4096 in `yt_chapters.py`; `content: null` handling in `tools/openrouter.py` and `tools/deepseek.py`
- **2026-05-14** — `yt_export.py`: rename-skip logic fixed (compare new_stem not prefix); noisy output removed
- **2026-05-14** — `yt_upload.py`: `get_or_create_playlist` → `find_existing_playlist` (error + exit if not found)
- **2026-05-14** — `scripts/yt_update_timestamps.py` created: adds missing YouTube chapter timestamps to uploaded video descriptions; uses `build_description()` from `uploader_common`; checks `0:` prefix to skip already-patched videos
- **2026-05-14** — Timing fix: `pr.bip()` added before timed operations (upload, encode, LLM); non-timed `pr.yes()` → `pr.green()` across 8 scripts

## Open Issues
None. Phase 11 implemented and verified.

## Errors / Repeated Mistakes (append; never overwrite)
- Phase 9 implemented `recordingDate` update instead of chapter-timestamp update — goal was misread. Corrected in Phase 10. Always confirm the concrete goal before implementing one-time utility scripts.
