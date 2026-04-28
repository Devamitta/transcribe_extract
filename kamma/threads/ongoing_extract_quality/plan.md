# Ongoing Extract Quality Loop — Plan

## Architecture
Three-phase loop with two hard stops (model switches + approval gate):
- Phase 1 (fast model): evidence gathering
- Phase 2 (pro model): diagnosis and proposal
- Phase 3 (fast model): implementation + session log

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

### Task 1.2 — Select sample files
- List files in `output/extracted/` (recursively)
- For each extracted file, find the corresponding source file in `output/corrected_pali/`
- List files in `output/extracted/interview/` only
- For each extracted file, find the corresponding source in `output/corrected_pali/interview/`
- Standard sample size: **all pairs that exist, up to 3 maximum**
  - If more than 3 pairs exist: prefer smallest + largest + most recently modified
  - If fewer than 3 exist: use all of them
- If no extracted files exist in `interview/`: report "No extracted files found in interview/ — nothing to evaluate" and exit

**Rationale for limit of 3:** Source files are 13,000–25,000 words each. We never read them fully — only word count + an 800-word sample per file. Three pairs = ~4,000 words of content in context, enough to identify systematic patterns. Beyond 3 adds no new signal.

→ verify: up to 3 pairs selected from `interview/` only

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

Produce a structured evidence block per file:
```
File: <filename>
Source words: ~N  |  Extracted words: ~M  |  Length ratio: X%
Traceability: N/3 traced, N/3 hallucinated
Format: [Q&A | paragraphs | mixed]
Notable issues: [brief description]
```
→ verify: evidence block produced for each pair

### Task 1.4 — ⛔ HARD STOP 1: Switch to pro model
Print exactly:
```
Evidence collected. Summary:

[paste the evidence blocks here]

Current system prompt:
[paste the full EXTRACT_SYSTEM_INSTRUCTION here]

Current chunk_text defaults: chunk_size=N, overlap=N

Switch to the pro model to continue with Phase 2 (analysis and proposal).
```
Stop here. Do not proceed further.

---

## Phase 2 — Diagnose and propose   ⟦ PRO MODEL ⟧

### Task 2.1 — Diagnose the root causes
Read the evidence blocks and the current system prompt. For each problem identified in the evidence (hallucination, over-compression, wrong format, over-filtering, etc.), state:
- What the symptom is
- What in the current prompt allows or causes it
- Confidence that the prompt change will fix it (1–10)
→ verify: each identified problem has a diagnosed cause

### Task 2.2 — Propose exact prompt changes
Write the complete proposed new `EXTRACT_SYSTEM_INSTRUCTION` string. Show a diff-style summary of what changed and why. Also propose any changes to `chunk_text` defaults if relevant. Be specific — the fast model will copy the proposed text verbatim.

Structure the proposal as:
```
PROPOSED CHANGES:

1. EXTRACT_SYSTEM_INSTRUCTION — full replacement:
[exact new string]

2. chunk_text defaults (if changing):
chunk_size: N → M  (reason: ...)
overlap: N → M  (reason: ...)

RATIONALE:
- Change X fixes problem Y because ...
- Change X2 fixes problem Y2 because ...
```
→ verify: proposal is concrete, complete, and copy-pasteable

### Task 2.3 — ⛔ HARD STOP 2: User approval gate
Print:
```
Proposed changes are above. Review and modify as needed.

Once approved, reply "approved" (or describe any changes you want) and switch back to the fast model to implement Phase 3.
```
Do not implement anything. Wait for explicit user approval.

---

## Phase 3 — Implement and log   ⟦ FAST MODEL ⟧

### Task 3.1 — Apply approved changes to `tools/extract.py`
- Replace `EXTRACT_SYSTEM_INSTRUCTION` with the approved string exactly as approved
- If chunk_text defaults were approved: update `chunk_text` function signature defaults
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

### Task 3.4 — Log session to handoff.md
Append to `kamma/threads/ongoing_extract_quality/handoff.md`:
- Date
- Files evaluated (list)
- Problems identified (brief)
- Changes applied (brief summary — not the full prompt)
- Test command printed
- Any issues or deferred items

→ verify: handoff.md updated; **plan.md is untouched** (no checkmarks, no session data, no appended notes)

---

## Errors & Issues Log
_Append new findings here; never overwrite previous entries._
