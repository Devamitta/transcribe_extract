# Plan: Tims Audio Pipeline

## Overview

Implement a Tims-specific workflow that adds folder-aware transcription, unchunked metadata suggestion generation, and a separate approval-driven export step based on an edited markdown review artifact.

## Phase 1: Plan Mode

### Task 1: Analyze context and confirm interfaces
- [x] Review the current behavior of `scripts/transcribe.py`, `scripts/extract_dhamma.py`, and relevant provider utilities.
- [x] Confirm the expected Tims paths: `audio/tims/`, `output/transcribed/tims/`, and `output/audio-tims/`.
- [x] Define the CLI contract for folder-specific transcription without breaking the default audio workflow.
- [x] Define the CLI contract for the new metadata script, including batch mode and single-file test mode.

Acceptance criteria:
- [x] The implementation model can describe exact CLI usage for both scripts before changing code.

Phase completion:
- [x] Verify the planned interfaces match `kamma/threads/20260408_tims_audio_pipeline/spec.md`.

## Phase 2: Execution

### Task 1: Add folder-aware transcription support
- [x] Update `scripts/transcribe.py` to accept a custom input folder.
- [x] Update `scripts/transcribe.py` to accept a custom output folder.
- [x] Preserve current default behavior for the top-level `audio/` flow.
- [x] Keep directory creation and skip/resume behavior intact.

Acceptance criteria:
- [x] Running the script with Tims-specific paths targets `audio/tims/` and writes to `output/transcribed/tims/`.
- [x] Running the script with no custom arguments still behaves as it does now.

### Task 2: Build the metadata suggestion script
- [x] Create a new script that reads transcript markdown files from the Tims transcription output.
- [x] Reuse the existing provider abstraction instead of adding a separate API integration path.
- [x] Send one full markdown file per request; do not implement chunk splitting for this workflow.
- [x] Generate a structured result containing a suggested upload title and a concise YouTube upload description.
- [x] Support both directory processing and a single-file testing mode.
- [x] Write one combined markdown review file with original filename, suggested title, and suggested upload description for each transcript.

Acceptance criteria:
- [x] The script works on one specific transcript file for testing.
- [x] The script works on the Tims transcript directory for batch generation.
- [x] The review markdown is readable and complete enough for manual approval and editing.

### Task 3: Build approved export packaging
- [x] Implement a separate rename/export script.
- [x] Read the edited combined markdown review file as the source of truth for approved titles and upload descriptions.
- [x] Rename only generated files, not original MP3 inputs.
- [x] Write approved outputs into `output/audio-tims/`.
- [x] Generate per-item markdown output containing approved title and approved upload description.
- [x] Generate an aggregate markdown file containing all approved titles and upload descriptions together.
- [x] Ensure filename sanitization is stable and filesystem-safe.

Acceptance criteria:
- [x] Approved outputs under `output/audio-tims/` match the edited review markdown exactly.
- [x] The rename/export step can be rerun safely without damaging source audio files.

Phase completion:
- [x] Verify the workflow runs automatically through suggestion generation and stops cleanly at the human review checkpoint.

## Phase 3: Verification

### Task 1: Validate code quality
- [x] Run `uv run ruff check --fix` on all changed Python files.
- [x] Run `uv run ruff format` on all changed Python files.

Acceptance criteria:
- [x] Ruff check and format complete without remaining issues on changed files.

### Task 2: Perform empirical verification
- [x] Run the updated transcription flow on at least one safe Tims target or subset.
- [x] Run the metadata script in single-file test mode.
- [x] Run the metadata script in batch mode if safe and practical.
- [x] Verify the review markdown content is usable for human editing.
- [x] Run the rename/export step against approved review data.

Acceptance criteria:
- [x] Real outputs are produced in the expected directories.
- [x] Suggested upload titles and descriptions are reviewable before export.
- [x] Exported markdown artifacts and filenames match the approved review data.

### Task 3: Prepare handoff and review
- [~] Present the final result to the user.
- [ ] Provide the exact line-by-line diff for changed files.
- [ ] Prepare a single draft commit command without executing it.
- [ ] Wait for user approval before the thread is marked complete.

Acceptance criteria:
- [ ] The user has a clear review checkpoint before completion.

Phase completion:
- [ ] Verify the thread remains in review until the user explicitly approves completion.

## Future Follow-up

- [ ] Extract the confirmed workflow into a reusable template under `kamma/tims/` after this thread is proven stable.
- [ ] Define the pause/resume verification point explicitly in that template so future runs stop cleanly for human review.
