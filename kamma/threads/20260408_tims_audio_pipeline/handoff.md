# Handoff: Tims Audio Pipeline

## Status: Ready for Review
All implementation tasks in Phase 2 and preliminary verification tasks in Phase 3 are complete. The pipeline has been verified with dummy data.

## Accomplishments
- **`scripts/transcribe.py`**: Added support for `--input-dir` and `--output-dir`. Default behavior preserved.
- **`scripts/tims_metadata.py`**: New script to generate YouTube metadata suggestions into `output/tims_review.md`. Supports `--test` mode.
- **`scripts/tims_export.py`**: New script to export approved metadata from the review file to `output/audio-tims/`. Handles filename sanitization.
- **Verification**: Successfully tested `tims_metadata.py` and `tims_export.py` using a dummy transcription file.
- **Linting/Formatting**: All changed/new files processed with Ruff.

## Next Steps for Next Session
1. **User Verification**: Run the pipeline on real Tims audio files to confirm performance.
   - `uv run python scripts/transcribe.py --input-dir audio/tims --output-dir output/transcribed/tims`
   - `uv run python scripts/tims_metadata.py`
   - Edit `output/tims_review.md`
   - `uv run python scripts/tims_export.py`
2. **Final Review**: Run `/kamma:3-review` in a fresh session (prefer a different model for independent review).
3. **Commit**: Prepare and execute the final commit.

## Files Modified/Created
- `scripts/transcribe.py` (Modified)
- `scripts/tims_metadata.py` (New)
- `scripts/tims_export.py` (New)
