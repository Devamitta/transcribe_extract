# Ongoing Semantic Evaluation Loop — Spec

## Overview
A recurring session thread for reviewing and fixing semantic hallucinations in corrected Pali transcripts. The evaluator identifies passages where Whisper substituted Pali words or made grammatical errors that degrade Dhamma extraction. When issues are found, an agent reviews findings with the user, applies approved fixes to `output/corrected_pali/` files, and re-evaluates to confirm clean. If no issues, the thread does not start.

## Prerequisite
- `scripts/evaluate_semantic.py` and `scripts/batch.py` exist and are operational
- User has access to the evaluation pipeline and can run scripts

## Entry point
User triggers this thread when they want to evaluate transcripts for semantic issues. The loop handles:
1. Running the evaluator (user chooses between direct or batch mode)
2. Reading the generated report
3. Classifying and planning fixes (with pro model)
4. Applying fixes and re-evaluating (with fast model)

## Two evaluation modes
- **Direct mode:** `uv run python scripts/evaluate_semantic.py <folder>` → produces `reports/semantic_anomalies_<timestamp>.md`
- **Batch mode:** `uv run python scripts/batch.py --stage semantic` → produces per-file reports in `reports/semantic/<filename>.md`
Both produce identical JSON report format (passage, issue, suggestion). User chooses based on cost/speed preference.

## Affected files
- `output/corrected_pali/**/*.md` — files that receive corrections
- `temp/apply_semantic_fixes.py` — one-off fix script, written and deleted per session
- `tools/pali.py` — `get_semantic_eval_instruction()` may be updated with new patterns
- `kamma/threads/ongoing_semantic_evaluation_loop/handoff.md` — session log

## Constraints
- Never modify `output/transcribed/` — only `output/corrected_pali/`
- Always verify changes with `git diff` before accepting
- Do not apply suggestions without explicit user approval
- `temp/apply_semantic_fixes.py` is gitignored and must be deleted after each session

## How we'll know it's done (per session)
- All user-approved fixes applied to `output/corrected_pali/` files
- Re-evaluation shows no remaining issues for passages that were fixed
- Prompt improvements (if any) applied to `tools/pali.py`
- Session logged in `handoff.md` with: timestamp, files processed, fixes applied, prompt changes, skipped findings, issues encountered
- `temp/apply_semantic_fixes.py` deleted

## What's not included
- Automated approval — all fixes require explicit user review
- Modifying the evaluator logic itself (belongs in `feature_semantic_evaluator` thread)
- Evaluating transcripts that have not been Pali-corrected
