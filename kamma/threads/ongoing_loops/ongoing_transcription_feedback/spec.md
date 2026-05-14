# Ongoing Transcription Quality Feedback Loop

## Goal
Establish a continuous loop of error analysis and filter refinement for Whisper transcriptions.

## Context
We have built tools (`extract_errors.py`, `diff_reports.py`, `extract_snippets.py`) to identify loops, silence hallucinations, and other common transcription issues.

## Strict Scope
**CRITICAL:** This thread is EXCLUSIVELY focused on the core transcription process.
- **In Scope:** `scripts/transcribe.py`, `transcribe.sh`, `transcribe-sangha.sh`, `transcribe-interview.sh`, `output/transcribed/`.
- **Out of Scope:** Post-processors (e.g., `correct_pali.py`), extraction scripts, or any other pipeline steps.
- **FORBIDDEN PATHS:** Do NOT read `output/extracted/`, `reports/semantic/`, or any `evaluate_pali` reports. These are handled by other threads.

## Process
1.  **Error Identification:** Run error extraction tools (`extract_errors.py`, `diff_reports.py`) on new transcription batches in `output/transcribed/`.
2.  **Branching Logic (HARD EXIT):**
    - **IF 0 ERRORS:** Print "All good!", log the result, and STOP. Do not look for errors elsewhere.
    - **IF ERRORS FOUND:** Proceed to AI Analysis.
3.  **AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - STOP AND SWITCH MODEL):** The initial implementation may happen via a lower-reasoning model, but the analysis of the errors MUST happen via a high-tier LLM (e.g., Sonnet 3.5/Opus). **STOP here and explicitly ask the user to switch the model.** Do NOT proceed to analysis until the user has confirmed the switch. Assess if the script has reached its practical limit (diminishing returns). If so, propose concluding the thread.
4.  **Improvement Proposal (CRITICAL MANDATE - STOP AND REVIEW PLAN):** If improvements are still viable, come up with a detailed improvement plan for the filters. **STOP here and wait for the user to review and approve the plan.** Do NOT proceed to implementation until the user has confirmed.
5.  **Filter Hardening:** Implement approved regex and logic improvements STRICTLY within `scripts/transcribe.py`.
6. **Manual Data Correction:** Create a temporary Python script to apply the approved changes directly to the *existing* output files to preserve data integrity without re-running the batch.
7. Write handoff and stop — user only needs to run the next batch for *new* data.