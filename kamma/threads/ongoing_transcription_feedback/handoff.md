# Handoff: Ongoing Transcription Quality Feedback Loop (2026-04-10)

## Status: Resolved Major Truncation Bug
The iteration was triggered by the observation that 3-hour audio files were producing very short (13-minute) transcripts.

### Fixes Implemented
1.  **Poisoned Context Bug (`scripts/transcribe.py`)**:
    *   **Issue**: Hallucination filters used `continue`, bypassing the paragraph-reset logic. Once a loop was "poisoned" in the context, every subsequent segment was dropped.
    *   **Fix**: Refactored to a `skip_segment` flag. Paragraph chunking/resetting now runs regardless of whether the current segment was skipped.
    *   **Improvement**: Replaced global regex checks with localized substring matches for better performance and fewer false positives.

2.  **Doubled Folder Bug**:
    *   **Issue**: redundant path calculations caused files to be saved in `output/transcribed/sangha/sangha/`.
    *   **Fix**: Simplified path logic in `scripts/transcribe.py` and synchronized `--output-dir` arguments in `transcribe-sangha.sh` and `transcribe-interview.sh`.

### Verification
- **Test File**: `audio/dhamma/2024-11-26 Sabbasava Sutta (MN2).mp3`
- **Result**: Full 16:32 duration transcribed correctly (previously truncated).
- **Linter**: Passed `ruff check` and `ruff format`.

### Next Steps
- [ ] User to run `./transcribe-sangha.sh` to re-process the 3-hour meetings.
- [ ] Establish new baseline error reports using `scripts/extract_errors.py` on the full-length transcripts.

### Errors & Repeated Mistakes
- **Background Processes**: Background processes via `run_shell_command` may terminate when the turn context ends if not properly detached. Use `nohup` for long-running transcription tasks, or better, run them locally outside the AI session to monitor progress in real-time.

## Update: Phrase Loop Filter Refinement (2026-04-11)

### Status: Improved Hallucination Detection
The second iteration focused on catching "Sentence Loop Hallucinations" that were slipping through the previous filters.

### Fixes Implemented
1.  **Enhanced Phrase Loop Filter (`scripts/transcribe.py`)**:
    *   **Issue**: Previous filter required exact punctuation matches and >15 characters. Hallucinations like `"It's possible. It's possible."` or `"what they mentioned, what they mentioned,"` were ignored.
    *   **Fix**: Implemented a punctuation-agnostic two-tiered check:
        *   **Short Phrase (5+ chars)**: 3+ repetitions (e.g., `"it s possible it s possible it s possible"`).
        *   **Long Phrase (15+ chars)**: 2+ repetitions (e.g., `"what they mentioned what they mentioned"`).
    *   **Logic**: Comparisons are now performed on cleaned text (lowercase, no punctuation, single spaces).

### Verification
- **Regex Testing**: Verified against 5 specific hallucinated samples from `log/error_report_20260411.md`. All samples are now correctly identified as skips.
- **Linter**: Passed `ruff check` and `ruff format`.

### Next Steps
- [ ] User to run `./transcribe-sangha.sh` and verify the reduction of phrase loops in the final markdown files.
- [ ] Run `/kamma:3-review` in a fresh session with a different model (e.g., switch from Opus to Sonnet 3.5 or vice-versa) for an independent architectural and logic review.

### Errors & Repeated Mistakes
- **Bash vs Python**: `transcribe-sangha.sh` is a shell script. Attempting to run it with `python` or `uv run python` results in a `SyntaxError` at the `echo ""` line. Use `./transcribe-sangha.sh` or `bash transcribe-sangha.sh`.

## Update: Refined Error Reporting & Hallucination Analysis (2026-04-11 V3)

### Status: False Positive Reduction in Error Reports
Iteration 3 focused on analyzing the latest transcription output with a "higher model" (Sonnet 3.5/Opus) and refining the reporting tools to distinguish between real Whisper hallucinations and natural speech stutters.

### Fixes Implemented
1.  **Tiered Repetition Check (`scripts/extract_errors.py`)**:
    *   **Issue**: The previous regex `(.{15,})\1{1,}` was too aggressive, flagging any 15+ character sequence that repeated exactly once. This caused many natural speech disfluencies (e.g., *"we should think we should think"*) to be reported as hallucinations.
    *   **Fix**: Implemented a tiered approach in the `identify_anomaly` function:
        *   **Medium Phrases (15-30 chars)**: Must repeat twice (appear 3 times) to be flagged.
        *   **Long Phrases (>30 chars)**: Must repeat once (appear 2 times) to be flagged.
    *   **Benefit**: This allows natural stutters (which usually only repeat once) to pass while still catching real Whisper loops.

### Verification
- **Baseline Comparison**: Rerunning `extract_errors.py` on the `sangha` transcripts showed a reduction from 9 anomalies down to 1 real anomaly.
- **Anomaly Identified**: The remaining anomaly correctly flagged a triple repetition loop: *"I like answers. I like answers. I like answers."*
- **Linter**: Passed `ruff check` and `ruff format`.

### Next Steps
- [ ] User to review the refined error report in `log/error_report_20260411_103814.md`.
- [ ] Run `/kamma:3-review` in a fresh session using a different model (e.g., if currently on Sonnet, use Opus) to verify the new regex logic and ensure no regressions in hallucination detection.

### Errors & Repeated Mistakes
- **Over-sensitivity in Tools**: Tools like `extract_errors.py` must be slightly less sensitive than the `transcribe.py` filters to avoid "crying wolf" with false positives. Natural speech is messy; the reporting tool should prioritize identifying clear Whisper glitches over every single stutter.
