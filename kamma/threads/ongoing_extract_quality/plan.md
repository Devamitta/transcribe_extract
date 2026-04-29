# Ongoing Extract Quality Loop — Plan

## Architecture
Three-phase loop with two hard stops (model switches + approval gate):
- Phase 1 (fast model): evidence gathering → saves to temp file
- Phase 2 (pro model): diagnosis and proposal → reads from temp file
- Phase 3 (fast model): implementation + session log → deletes temp file

## Architecture Decisions
**Context Overflow Prevention:**
- SESSION_LIMIT = 10: Select at most 10 problematic files per session. If more than 10 exist, mark remaining as `pending_next_session` in ledger.json for pickup in the next session.
- Evidence findings saved to `temp/extract_findings_YYYY-MM-DD.md` instead of conversation (prevents context bloat).
- Pro model (Phase 2) reads temp file at startup, then appends diagnosis + proposals back to temp file; only summary printed to conversation.
- Phase 3 (fast model) reads temp file at startup to get approved proposals; implements from file, not conversation.
- Phase 3 deletes temp file after changes are logged.
- **Script Ownership & API Usage:** Running any script that makes external API requests (e.g., `scripts/batch.py`, `scripts/evaluate_*.py`, `scripts/extract_dhamma.py`, `scripts/polish_extract.py`, `scripts/correct_pali.py`) is strictly **OUT OF SCOPE** for the agent. The agent's role is to research issues and implement prompt/logic improvements. After improvements are applied, the agent MUST ONLY print the exact command for the user to run to verify the changes.

## Scope
- **Folder:** `output/interview/` only — both source (`output/corrected_pali/interview/`) and extracted (`output/extracted/interview/`)
- Do not analyze files from `sangha/`, `tims/`, or other subfolders

## Template rule — CRITICAL
This plan.md is a reusable template used identically every session. It must **never be modified during or after a session** — no checkmarks, no session notes, no appended findings. All session-specific data goes exclusively in `handoff.md`. If a future session requires changing the plan itself (new step, changed approach), that is a deliberate edit with user approval — not a by-product of running the session.

---

## Phase 1 — Collect evidence   ⟦ FAST MODEL ⟧

### Task 1.1 — Read current system prompt
- Read `tools/extract.py` — extract and display the full `EXTRACT_SYSTEM_INSTRUCTION` string
- Note the current `chunk_text` default parameters (chunk_size, overlap)
→ verify: current prompt and chunk settings visible in context

### Task 1.2 — Select sample files (smart selection to avoid re-analysis)
1. **Read session history:**
   - Read `kamma/threads/ongoing_extract_quality/ledger.json`
   - Extract list of files analyzed in previous sessions (one per session header)
   - Extract the "outcome" (ratio %, issues found, etc.) for each file
   - If no prior sessions: skip to step 2

2. **Categorize available files:**
   - List all files in `output/extracted/interview/`
   - Split into three buckets:
     - **Bucket A:** Files re-extracted since last session (mtime > last_run in ledger.json)
     - **Bucket B:** Files never analyzed (not in ledger.json history)
     - **Bucket C:** Files with "clean" outcome in prior sessions (no issues, no changes recommended)

3. **Select up to 10 pairs (SESSION_LIMIT):**
   - Prioritize Bucket A (verify prompt fixes worked) — take all files in this bucket, up to 10
   - If fewer than 10: add from Bucket B (new territory), up to 10 total
   - Never pick from Bucket C (already verified clean)
   - If multiple files in a bucket, prefer: smallest, largest, most recently modified
   - If more than 10 files after prioritization: mark excess files in ledger.json as `pending_next_session` for next session pickup
   - If fewer than 10 files available: use all

4. **Handle edge cases:**
   - If no files in any bucket: print "All files analyzed, none re-extracted. Nothing to evaluate." and exit
   - If only Bucket C files exist: print "All analyzed files had no issues. No re-extraction needed." and exit

**Rationale:** Prevent re-analyzing the same files unnecessarily. Prioritize verifying that prompt fixes actually worked. New files naturally enter Bucket B and get analyzed. Bucket C prevents wasted effort on already-verified good files.

→ verify: file selection logic uses ledger.json history; prioritizes new/re-extracted files


### Task 1.3 — Collect evidence for each pair
For each source/extracted pair:
1. Read the extracted file (`output/extracted/...`) fully — record word count
2. Check word count of source file (`wc -w`) — record it; do NOT read the full source into context
3. Compute length ratio: extracted words / source words (target ≥ 0.5)
4. Read the **first 800 words** of the source file only — enough to see what kind of content it is and check traceability
5. Spot-check traceability: pick 3 phrases from the extracted output and check whether they appear (verbatim or near-verbatim) in the 800-word source sample. Classify each as:
   - `traced` — the phrase appears in or closely mirrors the source
   - `hallucinated` — the phrase does not appear in the source sample at all
   - `unverifiable` — phrase not in the 800-word sample (cannot conclude either way)
6. Check format: is the output mostly Q&A? Mostly plain paragraphs? Mixed?
7. Note any obvious over-filtering or under-filtering

**Write findings to temp file (not conversation):**
- Append each evidence block to `temp/extract_findings_YYYY-MM-DD.md`
- Print a summary table to conversation (1 line per file: filename, ratio %, issues)
- Do NOT print full evidence blocks to conversation

Example evidence block (for temp file):
```
File: <filename>
Source words: ~N  |  Extracted words: ~M  |  Length ratio: X%
Traceability: N/3 traced, N/3 hallucinated
Format: [Q&A | paragraphs | mixed]
Notable issues: [brief description]
```
→ verify: evidence blocks written to temp file; summary table printed to conversation

### Task 1.4 — ⛔ HARD STOP 1: Switch to pro model
Print exactly:
```
Evidence collected. Summary table:

[paste the summary table here (1 line per file)]

Current system prompt:
[paste the full EXTRACT_SYSTEM_INSTRUCTION here]

Current chunk_text defaults: chunk_size=N, overlap=N

Detailed evidence blocks saved to: temp/extract_findings_YYYY-MM-DD.md

Switch to the pro model to continue with Phase 2 (analysis and proposal).
At startup, read the temp file to see full evidence for each file.
```
Stop here. Do not proceed further.

---

## Phase 2 — Diagnose and propose   ⟦ PRO MODEL ⟧

### Task 2.1 — Diagnose the root causes
**At startup:** Read `temp/extract_findings_YYYY-MM-DD.md` to see full evidence blocks for all analyzed files.

Then, for each problem identified in the evidence (hallucination, over-compression, wrong format, over-filtering, etc.), state:
- What the symptom is
- What in the current prompt allows or causes it
- Confidence that the prompt change will fix it (1–10)

**Write to temp file (not conversation):**
- Append a `## Phase 2 Output` section to the temp file
- Under it, create `### Root Cause Analysis` subsection
- Write full diagnosis there

**Print to conversation:** Only a summary table: `| Problem | Cause | Confidence |`

→ verify: diagnosis written to temp file; summary table printed to conversation

### Task 2.2 — Propose exact prompt changes
Write the complete proposed new `EXTRACT_SYSTEM_INSTRUCTION` string. Show a diff-style summary of what changed and why. Also propose any changes to `chunk_text` defaults if relevant. Be specific — the fast model will copy the proposed text verbatim.

**Write to temp file (not conversation):**
- Append this structure to the temp file under `## Phase 2 Output`:
  ```
  ### Proposed Changes
  
  1. EXTRACT_SYSTEM_INSTRUCTION — full replacement:
  [exact new string]
  
  2. chunk_text defaults (if changing):
  chunk_size: N → M  (reason: ...)
  overlap: N → M  (reason: ...)
  
  ### Rationale
  - Change X fixes problem Y because ...
  - Change X2 fixes problem Y2 because ...
  ```

**Print to conversation:** Only a summary: "N changes proposed: [list of changes]. See temp file for full details."

→ verify: full proposals written to temp file; summary printed to conversation

### Task 2.3 — ⛔ HARD STOP 2: User approval gate
Print:
```
Summary of findings and proposals above. Full diagnosis and proposals written to:
  temp/extract_findings_YYYY-MM-DD.md

Review the file. If approved, reply "approved" (or specify any changes you want).
Then switch back to the fast model to implement Phase 3.
```
Do not implement anything. Wait for explicit user approval.

---

## Phase 3 — Implement and log   ⟦ FAST MODEL ⟧

### Task 3.1 — Apply approved changes to `tools/extract.py`
**At startup:** Read `temp/extract_findings_YYYY-MM-DD.md`. Locate `## Phase 2 Output → Proposed Changes`. Extract the exact text for the new `EXTRACT_SYSTEM_INSTRUCTION` and any `chunk_text` defaults.

Then:
- Replace `EXTRACT_SYSTEM_INSTRUCTION` with the approved string exactly as written in temp file
- If chunk_text defaults were approved: update `chunk_text` function signature defaults exactly as written in temp file
- Do not change anything else in the file
→ verify: changes applied; read the file and confirm the new string is in place

### Task 3.2 — Lint and format
Run:
```
uv run ruff check --fix tools/extract.py && uv run ruff format tools/extract.py
```
→ verify: ruff exits without errors

### Task 3.3 — Print test command for user
Select a file that was identified as problematic in Phase 1 (one that showed hallucination or low length ratio). Print:
```
Changes applied. To test, delete the existing extracted file and re-run:

  rm output/extracted/<folder>/<filename>.md
  uv run python scripts/extract_dhamma.py output/corrected_pali/<folder>/<filename>.md

Then start a new session of this thread to evaluate the new output.
```
→ verify: command printed with correct paths from Phase 1 evidence

### Task 3.4 — Log session to handoff.md and cleanup
Append to `kamma/threads/ongoing_extract_quality/handoff.md`:
- Date
- Files evaluated (list)
- Problems identified (brief)
- Changes applied (brief summary — not the full prompt)
- Test command printed
- Any issues or deferred items
- [ ] Log session to `ledger.json`.
  - Update `ledger.json` with the current session state.
  - Archive old sessions from `handoff.md` to `archive/handoff_archive.md` (keep only the 2 most recent sessions).
- If >10 files were encountered: list files marked as `pending_next_session` for next session pickup

**Cleanup:** Delete `temp/extract_findings_YYYY-MM-DD.md`

→ verify: handoff.md updated; temp file deleted; **plan.md is untouched** (no checkmarks, no session data, no appended notes)

---

## Errors & Issues Log
_Append new findings here; never overwrite previous entries._
