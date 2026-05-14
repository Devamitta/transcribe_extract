# Ongoing Feedback Plan (Iterative)

## Current Objective
Monitor and refine transcription quality based on manual transcriptions and error reports.

## Architecture Decisions
**Context Overflow Prevention:**
- SESSION_LIMIT = 10: Process at most 10 error items per session. Mark excess as `pending_next_session` in ledger.json.
- Findings saved to `temp/transcription_findings_YYYY-MM-DD.md` instead of conversation.
- Pro model (Task X.4) reads temp file at startup; appends analysis to temp file; prints summary only.
- Pro model (Task X.5) reads temp file again; appends proposed improvements to temp file; prints summary only.
- Task X.6 reads temp file at startup to implement approved changes.
- Cleanup (Task X.7) deletes temp file.
- **Script Ownership & API Usage:** Running any script that makes external API requests (e.g., `scripts/batch.py`, `scripts/evaluate_*.py`, `scripts/extract_dhamma.py`, `scripts/polish_extract.py`, `scripts/correct_pali.py`) is strictly **OUT OF SCOPE** for the agent. The agent's role is to research issues and implement prompt/logic improvements. After improvements are applied, the agent MUST ONLY print the exact command for the user to run to verify the changes.

---

## Iteration Template (Copy for new logs)
- [ ] **Task X.1: Error Extraction**
  - [ ] Verify user has run `scripts/extract_errors.py` on the latest transcription output.
  - [ ] Select up to 10 error items (SESSION_LIMIT). If more exist, mark rest as `pending_next_session`.
  - [ ] Write error findings to `temp/transcription_findings_YYYY-MM-DD.md` (not conversation).
  - [ ] Print summary table to conversation.
- [ ] **Task X.2: Diff Comparison**
  - [ ] Verify user has run `scripts/diff_reports.py` to compare with previous known baselines.
- [ ] **Task X.3: Branching Logic (HARD STOP IF CLEAN)**
  - [ ] **IF 0 ERRORS:** Note "All good!", provide a brief summary of files checked, and **STOP IMMEDIATELY**. Do not look for other tasks or files.
  - [ ] **IF ERRORS FOUND:** Proceed to Task X.4.
- [ ] **Task X.4: AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - MANUAL MODEL SWITCH)**
  - [ ] **STOP EVERYTHING.** Explicitly tell the user: "Please switch to a high-tier LLM (Opus or Sonnet 3.5) for analysis before I proceed." Do NOT attempt to analyze the errors yourself using the current model. Wait for the user to confirm the model switch before moving to analysis.
  - [ ] At startup, read `temp/transcription_findings_YYYY-MM-DD.md` to see full error details.
  - [ ] Write analysis to temp file under `## Phase 2 Output → Analysis`. Print to conversation: summary table only.
  - [ ] **EVALUATE LIMITS:** Assess if the remaining anomalies are unfixable without causing excessive false positives. If the script has reached its practical limit (diminishing returns), state this clearly and propose concluding the thread instead of further tweaking.
- [ ] **Task X.5: Improvement Plan (CRITICAL MANDATE - PLAN REVIEW)**
  - [ ] At startup, read `temp/transcription_findings_YYYY-MM-DD.md` again for reference.
  - [ ] Based on analysis, come up with a detailed plan to improve `scripts/transcribe.py`.
  - [ ] Write full proposed improvements to temp file under `## Phase 2 Output → Proposed Improvements`. Print to conversation: summary only.
  - [ ] Print message: "Proposals in temp/transcription_findings_YYYY-MM-DD.md. Review and reply 'approved' (or specify changes). Then switch to fast model for Task X.6."
  - [ ] **STOP AND WAIT.** Wait for explicit user approval before moving to implementation.
- [ ] **Task X.6: Transcribe Script Hardening**
  - [ ] Read `temp/transcription_findings_YYYY-MM-DD.md`. Locate `## Phase 2 Output → Proposed Improvements`. Extract approved improvements.
  - [ ] Implement approved improvements EXCLUSIVELY to real-time filters in `scripts/transcribe.py` (copy text exactly from temp file). Do not modify post-processors.
  - [ ] Manual data correction. Create a temporary script to apply fixes to existing transcriptions without re-running the entire process.
- [ ] **Task X.7: Verification & Cleanup**
  - [ ] Log session to `kamma/threads/ongoing_transcription_feedback/ledger.json`.
  - Update `ledger.json` with the current session state.
  - Archive old sessions from `handoff.md` to `archive/handoff_archive.md` (keep only the 2 most recent sessions).
  - [ ] Delete `temp/transcription_findings_YYYY-MM-DD.md`.
  - [ ] Instruct the user to run the relevant `transcribe*.sh` script for the next batch of files.