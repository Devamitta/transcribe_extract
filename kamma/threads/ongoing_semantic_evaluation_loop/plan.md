# Ongoing Semantic Evaluation Loop — Plan

## Architecture Decisions
- Three-phase workflow with three hard stops (user approval gates):
  - **Phase 1 (fast model):** Read batch-generated semantic reports, filter out already-reviewed reports, cap session at SESSION_LIMIT=10 files, write all findings to temp/semantic_findings_YYYY-MM-DD.md, print summary table to conversation only
  - **Phase 2 (pro model):** Read findings cache from temp file, classify findings, propose fixes and prompt improvements, wait for user approval
  - **Phase 3 (fast model):** Implement approved fixes, re-evaluate, update prompt, log session
- Replacements use `re.sub(r'\b' + re.escape(original) + r'\b', replacement, text, flags=re.IGNORECASE)` (consistent with `correct_pali.py`)
- Session entry point is fixed: user runs `uv run python scripts/batch.py --stage semantic` or `uv run python scripts/evaluate_semantic.py` before starting the thread
- `handoff.md` is the continuity mechanism for report-level review history: each reviewed report records its path, report mtime, and outcome so later sessions can skip unchanged reports
- `SESSION_LIMIT = 10`: max fresh files processed per session; excess files are logged as `pending_next_session` in ledger.json and picked up in the next run
- `temp/semantic_findings_YYYY-MM-DD.md`: ephemeral findings cache written by Phase 1, read by Phase 2 at startup, deleted in Task 3.4; keeps conversation context small
- **Script Ownership & API Usage:** Running any script that makes external API requests (e.g., `scripts/batch.py`, `scripts/evaluate_*.py`, `scripts/extract_dhamma.py`, `scripts/polish_extract.py`, `scripts/correct_pali.py`) is strictly **OUT OF SCOPE** for the agent. The agent's role is to research issues and implement prompt/logic improvements. After improvements are applied, the agent MUST ONLY print the exact command for the user to run to verify the changes.

---

## Phase 1 — Load fresh semantic reports   ⟦ FAST MODEL ⟧

### Task 1.1 — Select only fresh reports
- Assume the user already ran: `uv run python scripts/batch.py --stage semantic` or `uv run python scripts/evaluate_semantic.py`
- Read `kamma/threads/ongoing_semantic_evaluation_loop/ledger.json`
- Build a review ledger (ledger.json) from prior sessions mapping each semantic report path to the last reviewed report mtime and outcome
- List files in `reports/semantic/interview/`
- Split reports into buckets:
  - **Bucket A:** report files never reviewed before
  - **Bucket B:** report files whose current mtime is newer than the last reviewed mtime recorded in `handoff.md`
  - **Skip:** report files whose mtime is older than or equal to the last reviewed mtime already logged in `handoff.md`
- Merge Bucket A and Bucket B into a `fresh_list`; sort by Bucket A first, then Bucket B by mtime ascending
- Apply session cap:
  - Define `SESSION_LIMIT = 10`
  - If `len(fresh_list) > SESSION_LIMIT`:
    - `selected` = first SESSION_LIMIT files from fresh_list
    - For remaining files beyond the limit: append to handoff.md one line per file: `pending_next_session: <report_path>`
    - Print: "N fresh reports found. Processing first SESSION_LIMIT. Run the loop again for the remaining X."
  - Else: `selected` = all files in fresh_list
- If `selected` is empty: print "No new semantic reports since last review. Nothing to analyze." and exit
→ verify: with 20 fresh files, only 10 are loaded; the other 10 appear as `pending_next_session` entries in ledger.json; next session picks them up as Bucket A entries

### Task 1.2 — Read the fresh report files
- Read every report selected in Task 1.1
- Keep the report path and current file mtime with each report; this must be written back to `handoff.md` at the end of the session
- If a selected report contains only `_No anomalies detected._`: record it as `clean` for handoff purposes and do not send it to Phase 2
- If all selected reports are clean: print "No issues found in new semantic reports. Session complete." and update `handoff.md` with the reviewed clean reports
→ verify: all fresh reports are loaded; clean reports are logged and filtered out

### Task 1.3 — Write findings to temp file and print summary
- Determine today's date string: YYYY-MM-DD (use ISO 8601 format)
- Write ALL findings to `temp/semantic_findings_YYYY-MM-DD.md` using this structure:

  ```
  # Semantic Findings — YYYY-MM-DD

  ## File: <relative report path>
  ### Finding 1
  - **Passage:** [exact quote]
  - **Issue:** [explanation]
  - **Suggestion:** [proposed fix]

  ### Finding 2
  - **Passage:** [exact quote]
  - **Issue:** [explanation]
  - **Suggestion:** [proposed fix]

  (repeat for each finding)

  ## File: <next report path>
  (same structure)
  ```

- Print to conversation ONLY a summary table in this format:

  ```
  | File | Findings | Status |
  |------|----------|--------|
  | Ardmk 22-04-04.md | 8 | has issues |
  | Ardmk 22-05-24.md | 0 | clean |
  | (etc for all selected files)
  
  Total: N findings across M files (K clean, L with issues)
  ```

- Do NOT print individual passages, issues, or suggestions to the conversation. Keep only the table.
- Do NOT classify, judge, or propose fixes yet.

→ verify: temp/semantic_findings_YYYY-MM-DD.md exists, is readable, and contains all passages and findings in full; conversation shows only the summary table

### Task 1.4 — ⛔ HARD STOP 1: Switch to pro model
Print:
> "Findings written to temp/semantic_findings_YYYY-MM-DD.md (substitute actual date). Switch to the pro model. At the start of Phase 2, read that file before classifying."

Do not proceed further.

---

## Phase 2 — Analyse & plan   ⟦ PRO MODEL ⟧

### Task 2.1 — Classify each finding
- First action: read `temp/semantic_findings_YYYY-MM-DD.md` (check temp/ for the file matching today's date, or the most recent if date differs). This file contains all findings from Phase 1. Do not re-open the semantic report files or the corrected_pali source files — everything needed is in this temp file.

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

---

## ⛔⛔⛔ CHECKPOINT: MANDATORY Task 3.2b before proceeding ⛔⛔⛔

### Task 3.2b — ⛔ CRITICAL CHECKPOINT: Append deferred items to manual_corrections.md

**MANDATORY. DO NOT SKIP.** This must happen BEFORE Task 3.3 prompt improvements or any cleanup.

- Read the deferred_dhamma list from Phase 2 classification
- For EACH deferred item, append to `kamma/threads/ongoing_semantic_evaluation_loop/manual_corrections.md`:
  1. Create a new section with date header: `## Session X: YYYY-MM-DD`
  2. For each deferred term:
     - File reference (e.g., `### Ardmk 22-03-23`)
     - **Exact passage** from the transcript (full paragraph context)
     - **Evaluator's suggestion** (if any)
     - **Reason for deferral** (deferred_dhamma vs deferred_skip)
- If deferred list is EMPTY: explicitly state "No deferred Dhamma-Vinaya terms this session"
→ verify: manual_corrections.md file has been updated with all deferred items from this session

---

### Task 3.3 — Apply approved prompt improvements
- If Phase 2 proposed prompt changes: edit `get_semantic_eval_instruction()` in `tools/pali.py` exactly as approved
- Run: `uv run ruff check --fix tools/pali.py && uv run ruff format tools/pali.py`
→ verify: ruff passes without errors

### Task X.Verify — Print test command
- Print the command for the user to verify the changes:
  ```
  uv run python scripts/batch.py --stage semantic
  ```

## Phase 3.3b — Collaborative deferred review   ⟦ FAST MODEL ⟧

This phase runs immediately after Phase 3 if there are uncertain true positives (garbled terms where no confident replacement was found).

### Load deferred list from Phase 2
- Read the list of `deferred_dhamma` items already classified by the pro model in Phase 2
- Do NOT re-classify or re-evaluate relevance — the pro model has already done this
- If the list is empty: print "No deferred Dhamma-Vinaya terms to review." and skip to Task 3.4

### Append those items to manual_corrections.md with the necessary references and context
For each remaining deferred term, save:
1. The **exact passage** (full paragraph, not just the word)
2. The **evaluator's suggestion** (if any)
3. To kamma/threads/ongoing_semantic_evaluation_loop/manual_corrections.md in a new section with the date and file reference (e.g., "ARDMK 26-04-01")
- This file is meant for user to apply those corrections himself.

### Task 3.4 — ⛔⛔⛔ CRITICAL HANDOFF MAINTENANCE (DO NOT SKIP) ⛔⛔⛔

**MANDATORY HANDOFF HYGIENE:**
- **ONLY 2 SESSIONS IN handoff.md AT ALL TIMES.** No exceptions.
- **EVERY SESSION:** Archive the oldest of the current 2 sessions to `archive/handoff_archive.md` BEFORE logging the new session
- Step-by-step:
  1. Count the sessions currently in `handoff.md` (read the file to see `### Session N:` headers)
  2. If 3+ sessions exist: move the OLDEST session block (including all its details) to `archive/handoff_archive.md`
  3. Delete "Errors, issues, and repeated mistakes" entries for the archived session
  4. Result: `handoff.md` now contains exactly Sessions [N-1, N]; archive contains all older sessions
- **THIS IS NOT OPTIONAL.** Do not log new session until old sessions are archived.

**Session cleanup:**
- Delete `temp/apply_semantic_fixes.py`
- Delete `temp/semantic_findings_YYYY-MM-DD.md` (the findings cache written in Task 1.3)
- Update `ledger.json` with the current session state and remaining pending files
- Append NEW session entry to `kamma/threads/ongoing_semantic_evaluation_loop/handoff.md`:
  - `### Session X: YYYY-MM-DD` header
  - `last_run: YYYY-MM-DDTHH:MM:SSZ` (ISO 8601 timestamp — used by Phase 1 next session)
  - Date (human-readable)
  - Evaluation mode used (direct or batch)
  - Files processed (list or count)
  - Review ledger for this session:
    - `report: reports/semantic/interview/<filename>.md`
    - `report_mtime: YYYY-MM-DDTHH:MM:SSZ`
    - `outcome: clean | fixes_applied | deferred_only | false_positive_only | mixed`
  - Fixes applied (count + summary)
  - Prompt improvements made (if any)
  - Findings skipped (count + why)
  - Any issues encountered
  - Update "Errors, issues, and repeated mistakes" section with findings from this session only
- Ensure `plan.md` is unmodified (no session-specific notes or checkmarks). `plan.md` is a reusable template for the next session.

→ verify: 
  - `handoff.md` contains ONLY 2 sessions (N-1 and N)
  - older sessions moved to `archive/handoff_archive.md`
  - `ledger.json` updated
  - `temp/` files deleted
  - `plan.md` unchanged
