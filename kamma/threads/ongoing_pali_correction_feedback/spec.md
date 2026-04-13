# Ongoing Pali Correction Feedback Loop

## Goal
Establish a continuous loop of error analysis and prompt refinement for `correct_pali.py`.

## Context
We have built `scripts/evaluate_pali.py` to identify LLM hallucinations (conversational text, markdown injection) and structural errors (chunk mismatches, length discrepancies) in the Pali phonetic correction process.

## Strict Scope
**CRITICAL:** This thread is EXCLUSIVELY focused on the prompt and refinement of the Pali correction process.
- **In Scope:** `scripts/correct_pali.py` (specifically `system_instruction`), `scripts/evaluate_pali.py` (for report generation).
- **Out of Scope:** Whisper transcription (`scripts/transcribe.py`), structural logic changes to scripts, or adding new scripts. **DO NOT** modify these files under this thread.

## Process
1.  **Error Identification:** Run evaluation tools (`evaluate_pali.py`) on new corrected batches.
2.  **AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - STOP AND SWITCH MODEL):** The analysis of the errors MUST happen via a high-tier LLM (e.g., Sonnet 3.5/Opus). **STOP here and explicitly ask the user to switch the model.** Do NOT proceed to analysis until the user has confirmed the switch. Assess if the prompt has reached its practical limit (diminishing returns).
3.  **Improvement Proposal (CRITICAL MANDATE - STOP AND REVIEW PLAN):** If improvements are still viable, come up with a detailed improvement plan for the `system_instruction`. **STOP here and wait for the user to review and approve the plan.** Do NOT proceed to implementation until the user has confirmed.
4.  **Prompt Hardening:** Implement approved refinements STRICTLY within the `system_instruction` of `scripts/correct_pali.py`.
5.  **Verification:** Re-run `correct_pali.py` and `evaluate_pali.py` to verify the hallucinations are eliminated.
