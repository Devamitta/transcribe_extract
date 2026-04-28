# Ongoing Polish Quality Loop — Spec

## Overview
A recurring session thread for reviewing and improving the Dhamma polish pipeline. The fast model collects evidence (comparing extracted vs polished outputs), then hands off to the pro model for analysis and a concrete improvement proposal. Once the user approves the proposal, the fast model implements it. The user runs the polish scripts themselves to test.

## What This Thread Does NOT Do
- Does not run polish scripts
- Does not delete or re-generate polished files
- Does not re-process batches
- Only analyzes output and improves `POLISH_SYSTEM_INSTRUCTION` (and validation settings) in `tools/polish.py`

## Entry Point
User starts this thread when polishing output quality is unsatisfactory — output is over-compressed, loses content, introduces errors, or fails word count constraints.

## Loop Structure
1. **Phase 1 (fast model):** Read extracted and polished files, collect evidence, prepare structured findings
2. **⛔ HARD STOP 1:** Switch to pro model
3. **Phase 2 (pro model):** Analyze findings, diagnose root cause, propose prompt changes with exact diff
4. **⛔ HARD STOP 2:** User approves or modifies the proposed changes
5. **Phase 3 (fast model):** Apply approved changes, lint, print test command for user, log session

## Affected Files
- `tools/polish.py` — `POLISH_SYSTEM_INSTRUCTION` and validation settings (only file edited)
- `kamma/threads/ongoing_polish_quality/handoff.md` — session log

## Success Criteria (per session)
- Findings clearly document the gap between extracted and polished output
- Pro model proposes specific, testable prompt changes
- Changes applied to `tools/polish.py` and lint-clean
- Test command printed for user to run
- Session logged in `handoff.md`

## Constraints
- Never run polish scripts — print the command, let the user run it
- All prompt changes require explicit user approval before implementation
- Do not change scripts/polish_extract.py or other pipeline scripts (they import from tools/polish.py automatically)
