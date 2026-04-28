# Ongoing Batch Pali Feedback Plan (Iterative)

## Architecture Decisions
- Session = one pass: evaluate → analyze → implement → handoff
- `PALI_SYSTEM_INSTRUCTION` in `tools/pali.py` is the only file modified
- Handoff.md is the sole continuity mechanism between sessions; read it first
  every session to avoid re-attempting already-failed approaches
- **Script Ownership:** Running `scripts/batch.py` is strictly OUT OF SCOPE for the agent. The user runs it before starting a session and after the session is concluded.

---

## Session Template (copy one block per session)

### Task X.1 — Read Handoff & Evaluate Current Output
- [ ] Read `kamma/threads/20260427_ongoing_batch_pali_feedback/handoff.md` to
  understand what has already been attempted and what patterns are known
- [ ] Run: `uv run python scripts/evaluate_pali.py`
- [ ] Read the generated report: `reports/evaluate_pali_report_<timestamp>.md`
- [ ] **MANDATORY MANUAL SWEEP:** Run a `grep` or `ripgrep` sweep across ALL files in the output folder for known "Meaning Flip" patterns (e.g., vagina, winner, red cock, cook).
- [ ] List all anomalies by type: hallucinations, length discrepancy,
  word count change, chunk mismatch.
→ verify: report exists; anomaly count printed to stdout; manual sweep performed across all files; anomalies categorized

### Task X.2 — AI Analysis (CRITICAL MANDATE — STOP & SWITCH MODEL)
- [ ] STOP. Tell the user: "Please switch to Opus or Sonnet 4.x before I analyze."
- [ ] Wait for explicit confirmation of model switch before proceeding.
- [ ] After switch:
  - [ ] Categorize each anomaly by root-cause pattern
  - [ ] Cross-check against handoff — skip any pattern already attempted and failed
  - [ ] Diminishing returns check: if remaining anomalies are random or structurally
    unfixable via prompt engineering, state this clearly and propose concluding
→ verify: categorized error list presented with recommendation (continue OR conclude)

### Task X.3 — Propose Rule Changes (CRITICAL MANDATE — STOP & GET APPROVAL)
- [ ] For each proposed change show:
  - [ ] Which anomaly pattern it addresses
  - [ ] Current rule text (or "new rule" if adding)
  - [ ] Exact proposed new text
- [ ] STOP. Do NOT implement until the user explicitly approves.
→ verify: before/after presented for each rule; user has approved
→ verify: categorized error list presented with recommendation (continue OR conclude)

### Task X.4 — Implement Approved Changes
- [ ] File to edit: `tools/pali.py` — `PALI_SYSTEM_INSTRUCTION` string only
- [ ] File to edit: `tools/glossary.py` — non-core sections only
- [ ] Make exactly the approved changes, nothing more
- [ ] Run: `uv run ruff check --fix tools/pali.py && uv run ruff format tools/pali.py`
→ verify: ruff exits 0; `git diff` shows only the approved changes

### Task X.5 — Manual Data Correction
- [ ] Create a temporary Python script in `temp/apply_fixes.py` containing a dictionary of the approved `original -> corrected` mappings
- [ ] Run the script to update the current files in `output/corrected_pali/`
→ verify: script output shows files updated; spot check a file to confirm fix

### Task X.6 — Update Handoff and Stop
- [ ] Append a new dated entry to handoff.md with:
  - [ ] Session date and batch folder/context
  - [ ] Anomalies found (with counts)
  - [ ] Changes implemented (rule number, before → after)
  - [ ] Manual corrections applied to current data
  - [ ] Patterns deferred or deemed unfixable (with reason)
  - [ ] Errors or repeated mistakes encountered this session
- [ ] Tell the user: "Session complete. Current data has been manually patched. Run `scripts/batch.py --stage pali` only when you have a NEW batch ready."
→ verify: handoff.md updated with new dated entry; session declared complete