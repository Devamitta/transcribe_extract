# Ongoing Polish Quality — Plan

## Status
Thread ready. Run `/kamma:2-do @kamma/threads/ongoing_polish_quality/` when you need to improve polish quality.

## Architecture Decisions
**Context Overflow Prevention:**
- SESSION_LIMIT = 10: Select at most 10 files per session. If more than 10 exist, mark remaining as `pending_next_session` in ledger.json.
- Findings saved to `temp/polish_findings_YYYY-MM-DD.md` instead of conversation.
- Pro model (Phase 2) reads temp file at startup, then appends diagnosis + proposals back to temp file; only summary printed to conversation.
- Phase 3 (fast model) reads temp file at startup to get approved proposals; implements from file, not conversation.
- Phase 3 deletes temp file after changes logged.
- **Script Ownership & API Usage:** Running any script that makes external API requests (e.g., `scripts/batch.py`, `scripts/evaluate_*.py`, `scripts/extract_dhamma.py`, `scripts/polish_extract.py`, `scripts/correct_pali.py`) is strictly **OUT OF SCOPE** for the agent. The agent's role is to research issues and implement prompt/logic improvements. After improvements are applied, the agent MUST ONLY print the exact command for the user to run to verify the changes.

## Entry Conditions
Start this thread when:
- Polished output is over-compressed or loses content
- Output fails word count validation (±15% constraint)
- Output contains grammatical errors or artifacts
- Output appears to add information not in the extracted version
- Sentence rewriting is too aggressive or changes meaning

---

## Phase 1: Evidence Collection (Fast Model)

### Task 1.1: Select sample files to analyze
- [ ] Select up to 10 problematic polished files from output/polished/ (SESSION_LIMIT)
- [ ] Prioritize files with word count outside ±15% or known issues
- [ ] If more than 10 exist: mark excess as `pending_next_session` in ledger.json
- [ ] Note the specific problems: word count, content loss, readability issues
- [ ] Read both extracted and polished versions side-by-side for each

### Task 1.2: Collect detailed findings
- [ ] For each file, identify:
  - Input word count, output word count, % difference (flag if outside ±15%)
  - Specific sentences that were over-compressed or added content
  - Grammar or readability issues
  - Where POLISH_SYSTEM_INSTRUCTION failed or succeeded
- [ ] Write full findings to `temp/polish_findings_YYYY-MM-DD.md` (not conversation)
- [ ] Structure findings with line-by-line diffs showing problems
- [ ] Print a summary table to conversation (1 line per file: filename, %, issues)
- [ ] Prepare a concise summary of root cause patterns

### Task 1.3: Hand off to pro model
- [ ] Print summary table and this message:
  ```
  Findings collected. See summary above.
  Full details in: temp/polish_findings_YYYY-MM-DD.md
  
  Switch to pro model to analyze. At startup, read the temp file.
  ```
- [ ] Switch to pro model with this instruction:
  > "Read temp/polish_findings_YYYY-MM-DD.md to see full evidence. Diagnose root causes of polish quality issues. Propose specific changes to `tools/polish.py::POLISH_SYSTEM_INSTRUCTION` with exact before/after diffs. Changes must: (1) fix identified problems, (2) remain concrete and testable, (3) preserve ±15% word count constraint."

---

## Phase 2: Analysis & Proposal (Pro Model)

### Task 2.1: Diagnose root cause
- [ ] Analyze the collected evidence
- [ ] Identify why the prompt is failing: unclear constraints, conflicting directives, missing guidance
- [ ] Write diagnosis to `temp/polish_findings_YYYY-MM-DD.md` under `## Phase 2 Output → Root Cause Analysis`
- [ ] Print to conversation: summary table only (`| Problem | Cause | Impact |`)
- [ ] Explain the root cause clearly in the temp file

### Task 2.2: Propose changes with exact diffs
- [ ] Draft changes to `POLISH_SYSTEM_INSTRUCTION` with before/after code blocks
- [ ] Ensure changes are:
  - Specific (not vague)
  - Testable (changes can be verified)
  - Minimal (only fix the identified problems)
- [ ] Write full proposal to `temp/polish_findings_YYYY-MM-DD.md` under `## Phase 2 Output → Proposed Changes` (include full new `POLISH_SYSTEM_INSTRUCTION`)
- [ ] Print to conversation: one-line summary per change only
- [ ] Present the full proposal in the temp file for user review

### Task 2.3: Hand off to user for approval
- [ ] Print message:
  ```
  Summary of diagnosis above. Full proposals in: temp/polish_findings_YYYY-MM-DD.md
  
  Review the file. Reply "approved" (or specify changes) and switch to fast model for Phase 3.
  ```
- [ ] Wait for explicit user approval before proceeding
- [ ] User may review the temp file and request modifications

---

## Phase 3: Implementation (Fast Model)

### Task 3.1: Apply approved changes
- [ ] Read `temp/polish_findings_YYYY-MM-DD.md`. Locate `## Phase 2 Output → Proposed Changes`. Extract the new `POLISH_SYSTEM_INSTRUCTION`.
- [ ] Update `tools/polish.py::POLISH_SYSTEM_INSTRUCTION` with the approved text exactly as written in temp file
- [ ] Run `uv run ruff check --fix tools/polish.py`
- [ ] Run `uv run ruff format tools/polish.py`
- [ ] Verify no syntax errors: `uv run python -c "from tools.polish import POLISH_SYSTEM_INSTRUCTION; print(POLISH_SYSTEM_INSTRUCTION[:100])"`
- [ ] Commit changes if needed (follow git protocol from CLAUDE.md)

### Task 3.2: Print test command
- [ ] Print a test command for user to run, e.g.:
  > "To test the changes, run one of these:"
  > ```
  > PROVIDER=openrouter uv run python scripts/polish_extract.py --folder <folder_name> --test
  > ```
  > "Then review the polished output in output/polished/ and open a new session if further refinement is needed."

### Task 3.3: Log session and cleanup
- [ ] Update `kamma/threads/ongoing_polish_quality/handoff.md` with:
  - Session date
  - Files evaluated
  - Problems identified
  - Changes applied
  - Test command printed
  - If >10 files: list `pending_next_session` files
- [ ] Update `kamma/threads/ongoing_polish_quality/ledger.json` with:
  - Update `ledger.json` with the current session state.
  - Archive old sessions from `handoff.md` to `archive/handoff_archive.md` (keep only the 2 most recent sessions).
- [ ] Delete `temp/polish_findings_YYYY-MM-DD.md`

---

## Success Criteria (Per Session)
- Findings clearly explain the gap between extracted and polished output
- Pro model proposes specific, testable prompt changes
- Changes applied to `tools/polish.py` and lint-clean
- Test command printed for user to run
- Session logged in `handoff.md`
