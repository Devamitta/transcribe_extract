# Handoff

## How to Use This File
Read this before every session. It records what has been attempted, what worked,
what failed, and what patterns are known — so no session repeats prior mistakes.

All archived sessions are in this thread folder `archive/handoff_archive.md`. Only the 2 most recent sessions are kept in this file for quick reference.

---

## ⚠️ EVERY SESSION END — Handoff Maintenance Checklist

Before marking the session complete, run these steps:

- Move session [N-2] from this file to `archive/handoff_archive.md` (keep only sessions [N-1, N])
- Delete old session entries from "Errors, issues, and repeated mistakes" section
- Verify this file contains ONLY the 2 most recent sessions + their errors
- Verify `archive/handoff_archive.md` received the archived session
- Confirm `plan.md` is unchanged (reusable template for next session)

If you skip this, the next session's handoff will be 100+ lines too long. Don't skip.

---

## Handoff: Truncation False Positive Fix (Iteration 2026-04-28_B)

### 1. Analysis of Truncation Issues
- **Issue:** Two files (`Ardmk 22-12-31.md` and `Ardmk 24-11-13-2.md`) were flagged as **TRUNCATED** by `verify_duration.py`.
- **Root Cause:** Long run-on sentences without terminal punctuation (`.!?`) at the end of recordings caused paragraphs to grow up to ~125-130 seconds before flushing (120s threshold + final segment length). This exceeded the 120s gap allowed by `verify_duration.py`, triggering a false positive truncation report even though the text was present.

### 2. Improvements to `scripts/transcribe.py`
- **Lowered Force Flush Threshold:**
    - **Fix:** Reduced `is_force_flush` threshold from **120 seconds** to **90 seconds**.
    - **Result:** This ensures that paragraphs are flushed more frequently, bounding the maximum timestamp gap to ~100 seconds (90s + segment length), which is safely within the 120s tolerance of the verification tool.

### 3. Verification Results
- **Files Re-processed:** `Ardmk 22-12-31.md` and `Ardmk 24-11-13-2.md`.
- **Status:** **PASSED.** Running `verify_duration.py` now returns **OK** for all 109 interview transcripts.
- **Hallucinations:** `extract_errors.py` continues to report **0 anomalies** across the entire batch, confirming that the change did not introduce any regressions in filtering logic.

### 4. Next Steps
- The core transcription filters and flush logic have reached diminishing returns. 
- **FOR THE NEXT AGENT:** This thread is ready for final review. No further regex or timing tweaks are recommended for the current interview batch.

---

## Handoff: CJK Hallucination Filtering (Iteration 2026-04-28_C)

### 1. Analysis of the Latest Batch
- **Issue:** Identified 14 instances of the repeating Chinese characters "如此" (rúcǐ) in the latest transcription batch (115 files).
- **Nuance:** Unlike other hallucinations, these often appeared *inside* valid segments (e.g., `sentence... 如此如此... sentence.`). Dropping the entire segment would lose valid transcript data.

### 2. Improvements to `scripts/transcribe.py`
- **CJK Strip Filter:**
    - **Fix:** Implemented a direct regex substitution in the basic cleaning section: `text = re.sub(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\uFAFF\uFF66-\uFF9F]+", "", text)`.
    - **Result:** This strips out Chinese, Japanese, and Korean characters from the segment text *before* any other filters run. It preserves the valid English/Pali speech while silently removing the "如此" artifacts.

### 3. Manual Data Correction
- **Affected Files:** I applied a manual fix to the 9 affected files (`ARDMK 26-01-10.md`, `ARDMK 25-11-01.md`, `ARDMK 26-02-21.md`, etc.) using a temporary correction script. This cleaned the existing transcripts without requiring a full re-transcription.

### 4. Verification Results
- **Error Extraction:** Re-running `extract_errors.py` on the `output/transcribed/interview/` directory now returns **0 anomalies across 115 files**.
- **Visual Check:** Verified that valid English text surrounding the previous "如此" artifacts was preserved correctly.

### 5. Next Steps
- **FOR THE NEXT AGENT:** This thread is ready for review. All known structural and character-level hallucinations in the interview batch have been addressed.

### 6. Errors, Issues, and Repeated Mistakes
- **Issue:** Relying on `skip_segment = True` for "dirty" segments can cause data loss if the segment is a mix of valid speech and hallucinations.
- **Correction:** Use `re.sub` for specific, high-confidence hallucination patterns (like CJK in an English/Pali context) to clean the segment instead of dropping it.
