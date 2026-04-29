# Ongoing Pali Correction Feedback Plan (Iterative)

## Current Objective
Monitor and refine Pali correction quality by hardening the system prompt in `tools/pali.py`.

## Architecture Decisions
- **Prompt Location:** `tools/pali.py` → `get_pali_system_instruction(file_path)`
- **Direct Script:** `scripts/correct_pali.py` is the active execution path.
- **Context Overflow Prevention:**
  - SESSION_LIMIT = 10: Process at most 10 problematic items per session. Mark excess as `pending_next_session` in ledger.json.
  - Findings saved to `temp/pali_corrections_findings_YYYY-MM-DD.md` instead of conversation.
  - Pro model (Task X.2) reads temp file at startup; appends diagnosis to temp file; prints summary only.
  - Pro model (Task X.3) reads temp file again; appends proposed rules to temp file; prints summary only.
  - Task X.4 reads temp file at startup to implement approved changes.
  - Cleanup (Task X.5) deletes temp file.
- **Script Ownership & API Usage:** Running any script that makes external API requests (e.g., `scripts/batch.py`, `scripts/evaluate_*.py`, `scripts/extract_dhamma.py`, `scripts/polish_extract.py`, `scripts/correct_pali.py`) is strictly **OUT OF SCOPE** for the agent. The agent's role is to research issues and implement prompt/logic improvements. After improvements are applied, the agent MUST ONLY print the exact command for the user to run to verify the changes.

---

## Iteration Template (Copy for new logs)

- [ ] **Task X.1: Run Evaluation**
  - [ ] Verify user has run `scripts/evaluate_pali.py` on the latest corrected batch.
  - [ ] **CRITICAL:** Run manual grep sweep for semantic "meaning flip" patterns:
    ```bash
    grep -riE "vagina|winner|linear|epidemic|cookie|cook|cookies" output/corrected_pali/
    ```
  - [ ] Select up to 10 error items to fix (SESSION_LIMIT). If more exist, mark rest as `pending_next_session`.
  - [ ] Write error findings to `temp/pali_corrections_findings_YYYY-MM-DD.md` (not conversation).
  - [ ] Print summary table to conversation.

- [ ] **Task X.2: AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - MANUAL MODEL SWITCH)**
  - [ ] **STOP EVERYTHING.** Explicitly tell the user: "Please switch to a high-tier LLM (Opus or Sonnet 3.5) for analysis before I proceed." Do NOT attempt to analyze the errors yourself using the current model. Wait for the user to confirm the model switch before moving to analysis.
  - [ ] At startup, read `temp/pali_corrections_findings_YYYY-MM-DD.md` to see full error details.
  - [ ] Write diagnosis to temp file under `## Phase 2 Output → Analysis`. Print to conversation: summary table only.
  - [ ] **EVALUATE LIMITS:** Assess if the remaining anomalies are unfixable via prompt engineering. If the prompt has reached its practical limit (diminishing returns), state this clearly and propose concluding the thread.

- [ ] **Task X.3: Prompt Hardening Plan (CRITICAL MANDATE - PLAN REVIEW)**
  - [ ] At startup, read `temp/pali_corrections_findings_YYYY-MM-DD.md` again for reference.
  - [ ] Based on analysis, propose a set of new rules for `PALI_SYSTEM_INSTRUCTION` in `tools/pali.py`.
  - [ ] Write full proposed rules to temp file under `## Phase 2 Output → Proposed Rules`. Print to conversation: summary only.
  - [ ] Print message: "Proposals in temp/pali_corrections_findings_YYYY-MM-DD.md. Review and reply 'approved' (or specify changes). Then switch to fast model for Task X.4."
  - [ ] **STOP AND WAIT.** Wait for explicit user approval before moving to implementation.

- [ ] **Task X.4: Refine System Prompt**
  - [ ] Read `temp/pali_corrections_findings_YYYY-MM-DD.md`. Locate `## Phase 2 Output → Proposed Rules`. Extract approved rules.
  - [ ] Implement approved improvements strictly to `PALI_SYSTEM_INSTRUCTION` in `tools/pali.py` (copy text exactly from temp file).
  - [ ] Run: `uv run ruff check --fix tools/pali.py && uv run ruff format tools/pali.py`

- [ ] **Task X.5: Verification & Cleanup**
  - [ ] Log session to `kamma/threads/ongoing_pali_correction_feedback/handoff.md`.
  - [ ] Log session to `kamma/threads/ongoing_pali_correction_feedback/ledger.json`.
  - [ ] Archive old sessions from `handoff.md` to `archive/handoff_archive.md` (keep only the 2 most recent sessions).
  - [ ] Delete `temp/pali_corrections_findings_YYYY-MM-DD.md`.
  - [ ] Instruct the user to re-run `scripts/correct_pali.py` and verify with both `scripts/evaluate_pali.py` AND grep sweep.

---