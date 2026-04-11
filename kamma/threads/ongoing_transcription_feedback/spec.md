# Ongoing Transcription Quality Feedback Loop

## Goal
Establish a continuous loop of error analysis and filter refinement for Whisper transcriptions.

## Context
We have built tools (`extract_errors.py`, `diff_reports.py`, `extract_snippets.py`) to identify loops, silence hallucinations, and other common transcription issues.

## Process
1.  **Manual Transcription:** A human transcribes a file, or provides a known-good reference.
2.  **AI Analysis:** The automated reports identify potential errors in Whisper's output, this is done by higher AI model.
3.  **Filter Hardening:** AI proposes updates to `transcribe.py` (real-time filters) or `correct_pali.py` (post-processing).
4.  **Verification:** Test against previous known failures to ensure no regressions.
