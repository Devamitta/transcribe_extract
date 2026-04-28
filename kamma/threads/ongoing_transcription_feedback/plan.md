# Ongoing Feedback Plan (Iterative)

## Current Objective
Monitor and refine transcription quality based on manual transcriptions and error reports.

---

## Iteration Template (Copy for new logs)
- [ ] **Task X.1: Error Extraction**
  - [ ] Run `scripts/extract_errors.py` on the latest transcription output.
- [ ] **Task X.2: Diff Comparison**
  - [ ] Run `scripts/diff_reports.py` to compare with previous known baselines.
- [ ] **Task X.3: Branching Logic**
  - [ ] **IF 0 ERRORS:** Note "All good!" and skip to Verification (Task X.7).
  - [ ] **IF ERRORS FOUND:** Proceed to Task X.4.
- [ ] **Task X.4: AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - MANUAL MODEL SWITCH)**
  - [ ] **STOP EVERYTHING.** Explicitly tell the user: "Please switch to a high-tier LLM (Opus or Sonnet 3.5) for analysis before I proceed." Do NOT attempt to analyze the errors yourself using the current model. Wait for the user to confirm the model switch before moving to analysis.
  - [ ] **EVALUATE LIMITS:** Assess if the remaining anomalies are unfixable without causing excessive false positives. If the script has reached its practical limit (diminishing returns), state this clearly and propose concluding the thread instead of further tweaking.
- [ ] **Task X.5: Improvement Plan (CRITICAL MANDATE - PLAN REVIEW)**
  - [ ] Based on analysis, come up with a detailed plan to improve `scripts/transcribe.py`.
  - [ ] **STOP AND WAIT.** Present the plan to the user and wait for explicit approval before moving to implementation.
- [ ] **Task X.6: Transcribe Script Hardening**
  - [ ] Implement approved improvements EXCLUSIVELY to real-time filters in `scripts/transcribe.py`. Do not modify post-processors.
  - [ ] Manual data correction. Create a temporary script to apply fixes to existing transcriptions without re-running the entire process.
- [ ] **Task X.7: Verification**
  - [ ] Instruct the user to run the relevant `transcribe*.sh` script for the next batch of files.