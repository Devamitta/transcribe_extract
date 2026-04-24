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
  - [ ] Instruct the user to re-run `correct_pali.py` and `evaluate_pali.py` to verify.

---
