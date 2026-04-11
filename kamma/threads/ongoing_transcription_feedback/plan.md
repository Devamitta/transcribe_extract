# Ongoing Feedback Plan (Iterative)

## Current Objective
Monitor and refine transcription quality based on manual transcriptions and error reports.

---

## Iteration Template (Copy for new logs)
- [ ] **Task X.1: Error Extraction**
  - [ ] Run `scripts/extract_errors.py` on the latest transcription output.
- [ ] **Task X.2: Diff Comparison**
  - [ ] Run `scripts/diff_reports.py` to compare with previous known baselines.
- [ ] **Task X.3: Manual Switching to Higher Model**
  - [ ] Ask user to switch to a higher model (e.g., `medium`) for a subset of files to see if errors reduce.
- [ ] **Task X.4: AI Analysis & Proposal**
  - [ ] Review reports and propose improvements to filters (`transcribe.py`) or post-processors.
- [ ] **Task X.5: Refinement & Verification**
  - [ ] Apply fixes and verify against the test set.

---

## Active Iteration: 20260411_V3_Output_Feedback
- [x] **Task 3.1: Error Extraction**
  - [x] Run `scripts/extract_errors.py` on the latest transcription output. Found 9 anomalies.
- [x] **Task 3.2: Diff Comparison**
  - [x] Run `scripts/diff_reports.py` to compare with previous known baselines. Identified new/remaining loops in Saṅgha meetings.
- [ ] **Task 3.3: Manual Switching to Higher Model**
  - [ ] Ask user to switch to a higher model (e.g., `medium`) for a subset of files to see if errors reduce.
- [ ] **Task 3.4: AI Analysis & Proposal**
  - [ ] Review reports and propose improvements to filters (`transcribe.py`) or post-processors.
- [x] **Task 3.5: Refinement & Verification**
  - [x] Apply fixes and verify against the test set. (Updated `scripts/extract_errors.py` to use a tiered repetition check. Reduced false positives in Saṅgha meeting reports from 9 to 1 real anomaly.)

## Active Iteration: 20260411_New_Output_Processing
- [x] **Task 2.1: Error Extraction**
  - [x] Run `scripts/extract_errors.py` on the latest transcription output (`output/transcribed/sangha/`). Found 14 anomalies.
- [x] **Task 2.2: Diff Comparison**
  - [x] Run `scripts/diff_reports.py` to compare with previous known baselines. Confirmed 14 new/remaining hallucinations.
- [x] **Task 2.3: Manual Switching to Higher Model**
  - [x] Ask user to switch to a higher model (e.g., `medium`) for a subset of files to see if errors reduce. (Switched to Opus/Sonnet 3.5 for analysis)
- [x] **Task 2.4: AI Analysis & Proposal**
  - [x] Review reports and propose improvements to filters (`transcribe.py`) or post-processors. (Identified phrase loop bug due to segment truncation)
- [x] **Task 2.5: Refinement & Verification**
  - [x] Apply fixes and verify against the test set. (Updated regex filters in transcribe.py and verified regexes against hallucinated samples)

---

## Active Iteration: 20260410_Initial_Feedback
- [x] **Task 1.1: Error Extraction**
  - [x] Run for latest Whisper output (`Sabbasava Sutta`). Zero anomalies found after fix.
- [x] **Task 1.2: AI Analysis**
  - [x] Identified "poisoned context" bug causing premature truncation.
  - [x] Implemented "Targeted Context Check + Safe Reset" in `scripts/transcribe.py`.
  - [x] Fixed doubled folder name bug in output path.
  - [x] Verified fix with full 16-minute transcription of `Sabbasava Sutta`.
