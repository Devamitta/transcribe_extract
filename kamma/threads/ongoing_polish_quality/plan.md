# Ongoing Polish Quality — Plan

## Status
Thread ready. Run `/kamma:2-do @kamma/threads/ongoing_polish_quality/` when you need to improve polish quality.

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
- [ ] Choose 2–3 problematic polished files (real examples from output/polished/)
- [ ] Note the specific problems: word count, content loss, readability issues
- [ ] Read both extracted and polished versions side-by-side

### Task 1.2: Collect detailed findings
- [ ] For each file, identify:
  - Input word count, output word count, % difference (flag if outside ±15%)
  - Specific sentences that were over-compressed or added content
  - Grammar or readability issues
  - Where POLISH_SYSTEM_INSTRUCTION failed or succeeded
- [ ] Structure findings with line-by-line diffs showing problems
- [ ] Prepare a concise summary of the root cause patterns

### Task 1.3: Hand off to pro model
- [ ] Document all findings in `handoff.md` under the current session
- [ ] Switch to pro model with this prompt:
  > "Review the findings in kamma/threads/ongoing_polish_quality/handoff.md. Diagnose the root causes of polish quality issues. Propose specific changes to `tools/polish.py::POLISH_SYSTEM_INSTRUCTION` with exact before/after diffs. Your changes must: (1) fix the identified problems, (2) remain concrete and testable, (3) preserve the ±15% word count constraint."

---

## Phase 2: Analysis & Proposal (Pro Model)

### Task 2.1: Diagnose root cause
- [ ] Analyze the collected evidence
- [ ] Identify why the prompt is failing: unclear constraints, conflicting directives, missing guidance
- [ ] Explain the root cause clearly

### Task 2.2: Propose changes with exact diffs
- [ ] Draft changes to `POLISH_SYSTEM_INSTRUCTION` with before/after code blocks
- [ ] Ensure changes are:
  - Specific (not vague)
  - Testable (changes can be verified)
  - Minimal (only fix the identified problems)
- [ ] Present the proposal clearly for user review

### Task 2.3: Hand off to user for approval
- [ ] Wait for explicit user approval before proceeding
- [ ] User may modify the proposal

---

## Phase 3: Implementation (Fast Model)

### Task 3.1: Apply approved changes
- [ ] Update `tools/polish.py::POLISH_SYSTEM_INSTRUCTION` with the approved changes
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

### Task 3.3: Log session
- [ ] Update `kamma/threads/ongoing_polish_quality/handoff.md` with:
  - Session date
  - Problems identified
  - Changes applied
  - Test command printed

---

## Success Criteria (Per Session)
- Findings clearly explain the gap between extracted and polished output
- Pro model proposes specific, testable prompt changes
- Changes applied to `tools/polish.py` and lint-clean
- Test command printed for user to run
- Session logged in `handoff.md`
