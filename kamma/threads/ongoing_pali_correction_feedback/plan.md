# Ongoing Pali Correction Feedback Plan (Iterative)

## Current Objective
Monitor and refine Pali correction quality by hardening the system prompt using `evaluate_pali.py` reports.

---

## Iteration Template (Copy for new logs)
- [ ] **Task X.1: Run Evaluation**
  - [ ] Run `scripts/evaluate_pali.py` on the latest corrected batch.
- [ ] **Task X.2: AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - MANUAL MODEL SWITCH)**
  - [ ] **STOP EVERYTHING.** Explicitly tell the user: "Please switch to a high-tier LLM (Opus or Sonnet 3.5) for analysis before I proceed." Do NOT attempt to analyze the errors yourself using the current model. Wait for the user to confirm the model switch before moving to analysis.
  - [ ] **EVALUATE LIMITS:** Assess if the remaining anomalies are unfixable via prompt engineering. If the prompt has reached its practical limit (diminishing returns), state this clearly and propose concluding the thread.
- [ ] **Task X.3: Prompt Hardening Plan (CRITICAL MANDATE - PLAN REVIEW)**
  - [ ] Based on analysis, propose a set of new rules for the `system_instruction` in `scripts/correct_pali.py`.
  - [ ] **STOP AND WAIT.** Present the plan to the user and wait for explicit approval before moving to implementation.
- [ ] **Task X.4: Refine System Prompt**
  - [ ] Implement approved improvements strictly to the `system_instruction`.
- [ ] **Task X.5: Verification**
  - [x] Instruct the user to re-run `correct_pali.py` and `evaluate_pali.py` to verify.

---

## Active Iteration: 20260412_Iter_4_Tims
- [x] **Task 4.1: Run Evaluation**
  - [x] Ran `scripts/evaluate_pali.py` on `output/corrected_pali/tims/`. **0 anomalies found across 22 files.**
- [x] **Task 4.2: AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - MANUAL MODEL SWITCH)**
  - [x] **DIMINISHING RETURNS REACHED:** 0 anomalies found in the `tims` batch. The JSON diff strategy implemented in Iteration 3 has stabilized the process. No further prompt hardening required at this stage.
- [x] **Task 4.3: Prompt Hardening Plan (CRITICAL MANDATE - PLAN REVIEW)**
  - [x] No improvements needed.
- [x] **Task 4.4: Refine System Prompt**
  - [x] N/A (Stable).
- [x] **Task 4.5: Verification**
  - [x] Verified via `evaluate_pali.py` on 22 files in `output/corrected_pali/tims/`.

---

## Active Iteration: 20260412_Iter_3_Structural_JSON_Fix
- [x] **Task 3.1: Implement JSON Diff Strategy**
  - [x] Modified `system_instruction` in `scripts/correct_pali.py` to use JSON extraction.
  - [x] Updated `correct_pali_transcription()` to parse JSON and apply regex-based whole-word replacements.
  - [x] Archived old strategy to `scripts/archive/`.
- [x] **Task 3.2: Run Evaluation**
  - [x] Ran `scripts/correct_pali.py` on the `interview` batch.
  - [x] Ran `scripts/evaluate_pali.py`: **0 anomalies found across 5 files.** Structural parity is now guaranteed.

---

## Completed Iterations
### Active Iteration: 20260412_Iter_2_Interview
- [x] **Task 2.1: Run Evaluation**
  - [x] Ran `scripts/evaluate_pali.py` on `output/corrected_pali/interview/`. Found 207 anomalies.
- [x] **Task 2.2: AI Analysis & Diminishing Returns Check (CRITICAL MANDATE - MANUAL MODEL SWITCH)**
  - [x] Confirmed catastrophic failure (infinite loops, content swapping). Prompt engineering reached its limit.
- [x] **Task 2.3: Prompt Hardening Plan**
  - [x] Proposed structural JSON fix strategy to the user. Approved.
- [x] **Task 2.4: Refine System Prompt**
  - [x] **CANCELLED** in favor of structural fix.
- [x] **Task 2.5: Verification**
  - [x] **CANCELLED**

### Active Iteration: 20260412_Initial_Pali_Feedback
- [x] **Task 1.1: Run Evaluation**
  - [x] Ran evaluation on `output/transcribed/interview`. Found critical chunk mismatch errors.
- [x] **Task 1.2: AI Analysis (MANUAL MODEL SWITCH)**
  - [x] Confirmed existing prompt failures in `Ardmk 22-03-09.md` and others.
- [x] **Task 1.3: Prompt Hardening Plan**
  - [x] Proposed set of negative constraints (no AI intros, no markdown code blocks, no text deletion).
- [x] **Task 1.4: Refine System Prompt**
  - [x] Updated `scripts/correct_pali.py` with the hardened rules.
- [x] **Task 1.5: Verification**
  - [x] Verified initial run of the new prompt on the first few chunks of `ARDMK 26-04-01.md`.
