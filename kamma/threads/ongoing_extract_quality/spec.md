# Ongoing Extract Quality Loop — Spec

## Overview
A recurring session thread for reviewing and improving the Dhamma extraction pipeline. The fast model collects evidence (comparing source transcripts vs extracted outputs), then hands off to the pro model for analysis and a concrete improvement proposal. Once the user approves the proposal, the fast model implements it. The user runs the extraction scripts themselves to test.

## What This Thread Does NOT Do
- Does not run extraction scripts
- Does not delete or re-generate extracted files
- Does not re-process batches
- Only analyzes output and improves `EXTRACT_SYSTEM_INSTRUCTION` (and chunk settings) in `tools/extract.py`

## Entry Point
User starts this thread when extraction output quality is unsatisfactory — output is too short, too generic, hallucinated, or over-filtered.

## Loop Structure
1. **Phase 1 (fast model):** Read source and extracted files, collect evidence, prepare structured findings
2. **⛔ HARD STOP 1:** Switch to pro model
3. **Phase 2 (pro model):** Analyze findings, diagnose root cause, propose prompt changes with exact diff
4. **⛔ HARD STOP 2:** User approves or modifies the proposed changes
5. **Phase 3 (fast model):** Apply approved changes, lint, print test command for user, log session

## Affected Files
- `tools/extract.py` — `EXTRACT_SYSTEM_INSTRUCTION` and `chunk_text` defaults (only file edited)
- `kamma/threads/ongoing_extract_quality/handoff.md` — session log

## Success Criteria (per session)
- Findings clearly document the gap between source and extracted output
- Pro model proposes specific, testable prompt changes
- Changes applied to `tools/extract.py` and lint-clean
- Test command printed for user to run
- Session logged in `handoff.md`

## Constraints
- Never run extraction scripts — print the command, let the user run it
- All prompt changes require explicit user approval before implementation
- Do not change batch.py or other pipeline scripts (they import from tools/extract.py automatically)
