# Ongoing Semantic Evaluation Loop — Plan

## Architecture Decisions
- Three-phase workflow with three hard stops (user approval gates):
  - **Phase 1 (fast model):** Determine which files to evaluate, guide user to run evaluator script, read report and display findings
  - **Phase 2 (pro model):** Classify findings, propose fixes and prompt improvements, wait for user approval
  - **Phase 3 (fast model):** Implement approved fixes, re-evaluate, update prompt, log session
- Replacements use `re.sub(r'\b' + re.escape(original) + r'\b', replacement, text, flags=re.IGNORECASE)` (consistent with `correct_pali.py`)
- Report path determined by user's choice of evaluation script (direct or batch mode)
- Session metadata appended to `handoff.md` for tracking which files were processed and when

---

## Phase 1 — Scope & run evaluator   ⟦ FAST MODEL ⟧

### Task 1.1 — Determine which files need evaluation
- Read `kamma/threads/ongoing_semantic_evaluation_loop/handoff.md` for `last_run` timestamp (if exists)
- If no previous session: all files in `output/corrected_pali/` are new
- If previous session exists: identify files in `output/corrected_pali/` with mtime newer than `last_run` timestamp. These are files modified since last evaluation (by Pali correction pipeline or prior session fixes)
- If no files are newer: print "No files modified since last session. Nothing to evaluate." and exit
→ verify: correctly identify new or modified files based on last_run timestamp

### Task 1.2 — ⛔ HARD STOP 1: Present script options to user
Print exactly:
```
Files to evaluate: [list files or folder name]

Two ways to run the evaluator:

**Option A — Direct mode (fast, live):**
  uv run python scripts/evaluate_semantic.py <folder>
  Output: reports/semantic_anomalies_<timestamp>.md

**Option B — Batch mode (async, budget-friendly):**
  uv run python scripts/batch.py --stage semantic [--folder <folder>]
  Output: reports/semantic/<filename>.md

Both produce identical findings format (passage, issue, suggestion).
Choose based on your preference for speed vs. cost.

Once you run the script, report back: "Done, I ran [Option A or B]. Report is at: [path]"
```
Stop here. Wait for user to run script and report the report path.

### Task 1.3 — Read the report file
- User provides report path (e.g., `reports/semantic_anomalies_20260428_143022.md` or `reports/semantic/interview.md`)
- Open and read the full file
- If file is empty or contains "_No anomalies detected_": print "No issues found. Session complete." and exit
→ verify: report file exists and contains findings

### Task 1.4 — Display all findings verbatim
- Print all findings grouped by file
- For each finding, show:
  - **Passage:** [exact quote]
  - **Issue:** [explanation]
  - **Suggestion:** [proposed fix]
- At the end, print summary: "Found N findings across M files"
- Do NOT classify, judge, or propose fixes yet — just display

→ verify: all findings displayed in conversation context

### Task 1.5 — ⛔ HARD STOP 2: Switch to pro model
Print:
> "All findings are in context above. Please switch to the pro model to continue with Phase 2 (classification and planning)."

Do not proceed further.

---

## Phase 2 — Analyse & plan   ⟦ PRO MODEL ⟧

### Task 2.1 — Classify each finding
For each finding from Phase 1, decide: **true positive** (real Whisper error) or **false positive** (not an error).

For **false positives**, classify reason:
- `informal_speech` — casual teacher speech, not transcription error
- `teaching_example` — intentional analogy or metaphor
- `grammar` — spoken grammar imperfection (common in speech, not Whisper substitution)
- `valid_content` — theologically correct statement, incorrectly flagged
- `misquote` — evaluator cited wrong passage for finding
- `context_only` — garbled term in clearly non-Dhamma context (monk names, place names, monastery logistics, personal conversation). These passages will be removed in the next pipeline stage; do NOT spend time correcting them.

For **true positives**: these are real Whisper errors that need fixing.

**IMPORTANT for Pro model:** Before proposing a fix, ask: "Is this passage Dhamma-Vinaya content, or is it personal conversation about monks, places, or logistics?" If the latter, classify as `context_only` and skip — even if the garble is clear. Only fix terms that will remain meaningful after Dhamma extraction.

→ verify: each finding classified, reasoning clear

### Task 2.2 — Build fix list for true positives
For each true positive:
- If replacement is **known with confidence**: create a fix entry
- If replacement is **uncertain**: classify the term as one of:
  - `deferred_dhamma` — garbled Pali/Dhamma/Vinaya term worth resolving; queue for Phase 3b user review
  - `deferred_skip` — garbled monk name, place name, or logistical term; this content will be stripped in the next pipeline stage; no fix needed, do not queue for user review
  - This classification must be done by the pro model — the fast model will not re-evaluate it

```
{
  "file": "output/corrected_pali/folder/filename.md",
  "original": "exact wrong text from transcript",
  "replacement": "corrected text"   // or null if deferred
  "deferred": "dhamma" | "skip" | null
}
```
Present full list (confident fixes + deferred classification) to user for approval. User may:
- Approve as-is
- Reject individual items
- Manually edit original/replacement text
- Add new fixes
- Override deferred classification

→ verify: user explicitly approves fix list and deferred classifications

### Task 2.3 — Propose prompt improvements
Review false positives and true positives together:
- From **false positives**: suggest new DO NOT FLAG examples to add to `get_semantic_eval_instruction()` in `tools/pali.py` (cases the evaluator should skip)
- From **true positives**: suggest new ERROR PATTERNS to recognize (new Whisper garbles or Pali word substitutions found this session)

Present as a diff-style proposal — show exact text to add, to which section of the function.

→ verify: proposals are concrete and testable

### Task 2.4 — ⛔ HARD STOP 3: Present complete plan for approval
Print two sections:

> **A — Fixes to apply:**
> [list of all approved replacements from Task 2.2]
>
> **B — Prompt improvements:**
> [proposed additions to get_semantic_eval_instruction()]

Then:
> "Review the plan above. Make any edits you want. Once you approve, switch to the fast model and run Phase 3."

Do not implement anything. Wait for user approval.

---

## Phase 3 — Implement   ⟦ FAST MODEL ⟧

### Task 3.1 — Create and run fix script
- Create `temp/apply_semantic_fixes.py`:
  - First line: docstring describing this session's fixes in one sentence
  - For each file in the approved fix list:
    - Read original file, save backup to `temp/<filename>.bak`
    - For each replacement:
      - Apply: `re.sub(r'\b' + re.escape(original) + r'\b', replacement, text, flags=re.IGNORECASE)`
      - Print before→after using `difflib.unified_diff` on affected lines
    - Write modified text to original file
    - Print result: `pr.yes(f"{filename}: {n} replacement(s)")` or `pr.no(f"{filename}: no matches found")`
  - Use `from tools import printer as _p; pr = _p.printer`
- Run: `uv run python temp/apply_semantic_fixes.py`
→ verify: script runs without error; all changes visible in diff output

### Task 3.2 — Verify changes are correct
- Read the diff output from Task 3.1
- Confirm each changed line matches exactly one approved replacement from Phase 2
- If anything unexpected: restore from `temp/<filename>.bak` and report to user
- If all correct: delete `.bak` files from `temp/`
→ verify: all changes match approved fixes exactly; no extra or missed replacements

### Task 3.3 — Apply approved prompt improvements
- If Phase 2 proposed prompt changes: edit `get_semantic_eval_instruction()` in `tools/pali.py` exactly as approved
- Run: `uv run ruff check --fix tools/pali.py && uv run ruff format tools/pali.py`
→ verify: ruff passes without errors

### Task 3.4 — Clean up and log session
- Delete `temp/apply_semantic_fixes.py`
- Append to `kamma/threads/ongoing_semantic_evaluation_loop/handoff.md`:
  - `last_run: YYYY-MM-DDTHH:MM:SSZ` (ISO 8601 timestamp — used by Phase 1 next session)
  - Date (human-readable, e.g., "2026-04-28")
  - Evaluation mode used (direct or batch)
  - Files processed (list or count)
  - Fixes applied (count + summary)
  - Prompt improvements made (if any)
  - Findings skipped (count + why)
  - Any issues encountered
- Ensure `plan.md` is unmodified (no session-specific notes or checkmarks). `plan.md` is a reusable template for the next session.
→ verify: `temp/apply_semantic_fixes.py` deleted; `handoff.md` updated with timestamp; `plan.md` unchanged

---

## Phase 3b — Collaborative deferred review   ⟦ FAST MODEL ⟧

This phase runs immediately after Phase 3 if there are uncertain true positives (garbled terms where no confident replacement was found).

### Task 3b.1 — Load deferred list from Phase 2
- Read the list of `deferred_dhamma` items already classified by the pro model in Phase 2
- Do NOT re-classify or re-evaluate relevance — the pro model has already done this
- If the list is empty: print "No deferred Dhamma-Vinaya terms to review." and skip to Task 3.4

### Task 3b.2 — Present each deferred term for user review
For each remaining deferred term, show:
1. The **exact passage** (full paragraph, not just the word)
2. The **evaluator's suggestion** (if any)
3. Ask: "What should this be? (or type 'skip' to leave unchanged)"

Go one by one. Do not batch them. Wait for user response before showing the next.

### Task 3b.3 — Apply user-confirmed corrections
- For each term the user confirmed: add to fix list and apply using the same `re.sub` pattern
- Create a separate `temp/apply_semantic_fixes_deferred.py` script for these fixes
- Delete script and backups after verification
- Update `handoff.md` to include Phase 3b fixes in the session log

→ verify: all user-confirmed fixes applied; no context_only terms were presented to the user
