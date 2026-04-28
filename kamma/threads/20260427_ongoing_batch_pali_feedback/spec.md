# Ongoing Batch Pali Feedback Loop

## Overview
A recurring, single-session improvement loop for the OpenAI Batch Pali
correction pipeline. The user runs `scripts/batch.py --stage pali` between
sessions. Each session: evaluate the existing output, analyze errors, implement
approved prompt fixes in `tools/pali.py` or other relevant files, manually correct existing output, write a handoff, and stop.
**Diminishing Returns Principle:** This loop is not meant to be endless. Once the script is "good enough" and improvements become marginal, we will honestly admit we have reached the limit, stop improving, and conclude the thread to move on to other tasks.

## Architectural Note
Both `scripts/correct_pali.py` (Gemini, real-time) and `scripts/batch.py
--stage pali` (OpenAI, async) share the same `PALI_SYSTEM_INSTRUCTION` from
`tools/pali.py`. Prompt changes here apply to both pipelines.

## Session Structure (one pass per session)
1. Evaluate: run `evaluate_pali.py` on current `output/corrected_pali/`
2. Analyze errors with a high-tier LLM (STOP — switch model first)
3. Propose rule changes (STOP — get user approval)
4. Implement approved changes in `tools/pali.py` and `tools/glossary.py`
5. **Manual Data Correction:** Create a temporary Python script to apply the approved changes directly to the *existing* output files to preserve data integrity without re-running the batch.
6. Write handoff and stop — user only needs to run the next batch for *new* data.

## Strict Scope
- **In scope:** `tools/pali.py` (PALI_SYSTEM_INSTRUCTION only), `scripts/evaluate_pali.py`, `tools/glossary.py` (expanding non-core sections like EXTENDED_TERMS or new sections), **temporary scripts in `temp/` to apply manual fixes to current output.**
- **Out of scope (CRITICAL):** Running the `scripts/batch.py` script. The agent MUST NOT run the batch process. The agent only deals with the *existing* output provided by the user at the start of the session.
- **Other out of scope:** Batch infrastructure, chunking logic, extract stage,
  correct_pali.py internals
- **CRITICAL GLOSSARY RULE:** You MUST NOT touch the DHAMMA, SANGHA, or VINAYA categories in `tools/glossary.py`. You may ONLY add terms to other categories (like EXTENDED_TERMS or SUTTA_TERMS).

## Constraints
- **Execution Mandate:** The user runs `scripts/batch.py` *before* the session starts and *after* the session ends. The agent never triggers it.
- **Economy mandate:** Never ask the user to re-run the batch inside a session
- **Shared prompt:** Changes affect both pipelines (correct_pali.py + batch.py)
- **Handoff is mandatory:** Every session must end with an updated handoff.md
- **Avoid Endless Tweaking:** If the remaining anomalies are minor or unfixable without breaking other things, explicitly recommend concluding the loop instead of forcing an improvement.

## How We Know a Session Is Done
- All analyzable anomalies from the report are addressed or documented as
  unfixable
- `tools/pali.py` passes `uv run ruff check --fix` and `uv run ruff format`
- `handoff.md` is updated with this session's findings

## What's Not Included
- Running `scripts/batch.py` (user's responsibility between sessions)
- Verification runs
