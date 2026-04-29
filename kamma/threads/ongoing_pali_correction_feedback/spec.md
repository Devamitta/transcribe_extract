# Ongoing Pali Correction Feedback Loop

## Goal
Establish a continuous loop of error analysis and prompt refinement for the Pali correction process.

## Context
- `scripts/evaluate_pali.py` identifies structural errors (chunk mismatches, length discrepancies).
- **CRITICAL LIMITATION:** `evaluate_pali.py` CANNOT detect semantic "meaning flip" hallucinations (e.g., `vagina` → `paññā`, `winner` → `Vinaya`). Manual grep sweeps are mandatory.
- Prompt is shared between `scripts/correct_pali.py` (Gemini, real-time) and `scripts/batch.py` (OpenAI, async).

## Architecture
- **Prompt Location:** `tools/pali.py` → `get_pali_system_instruction(file_path)`
- **Folder-Aware Glossary:** Includes `MONASTICS` only for files in 'sangha' folder. Excludes for 'interview' folder to prevent over-correction.
- **Direct Script:** `scripts/correct_pali.py` is the active execution path for this loop.

## Strict Scope
**CRITICAL:** This thread is EXCLUSIVELY focused on the prompt and refinement of the Pali correction process.
- **In Scope:** `tools/pali.py` (PALI_SYSTEM_INSTRUCTION), `scripts/evaluate_pali.py` (report generation), `tools/glossary.py` (non-core sections).
- **Out of Scope:** Whisper transcription, structural logic changes to scripts, batch infrastructure. **DO NOT** modify these files under this thread.

## Process
1.  **Error Identification:** Run `evaluate_pali.py` AND perform manual grep sweep for semantic errors.
2.  **AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - STOP AND SWITCH MODEL):** The analysis of the errors MUST happen via a high-tier LLM. **STOP here and explicitly ask the user to switch the model.** Assess if the prompt has reached its practical limit.
3.  **Improvement Proposal (CRITICAL MANDATE - STOP AND REVIEW PLAN):** If improvements are still viable, come up with a detailed improvement plan. **STOP here and wait for user approval.**
4.  **Prompt Hardening:** Implement approved refinements to `tools/pali.py` (PALI_SYSTEM_INSTRUCTION).
5.  **Verification:** Re-run `scripts/correct_pali.py` and verify with both `evaluate_pali.py` AND grep sweep.

## Key Constraints
- **Evaluation limitation:** Automated scripts miss semantic meaning-flip errors. Always run `grep -riE "vagina|winner|linear|epidemic" output/corrected_pali/` to verify.
- **Economy mandate:** Never re-run expensive LLM work for trivial fixes. Manually patch current data instead.
- **Diminishing returns:** The prompt has been significantly hardened. Further improvements yield marginal returns. Monitor for regression, not expansion.