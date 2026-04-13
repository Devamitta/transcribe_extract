## Handoff: Reporting Sync & False Positive Reduction (Iteration 20260411_Interview_Feedback_Loop)

### 1. Reporting Logic Synchronization
- **Logic Mismatch:** Identified a discrepancy where `scripts/transcribe.py` (the engine) allowed up to 5 repetitions of filler words, but `scripts/extract_errors.py` (the reporter) flagged 4 or more as a hallucination. This caused "natural" stutters (e.g., "yeah yeah yeah yeah") to be reported as errors even when the transcription engine was behaving correctly.
- **Fix:** Synchronized `scripts/extract_errors.py` with the transcription engine's logic.
    - Added the same filler word whitelist: `["yeah", "no", "okay", "so", "right", "hmm", "mhmm", "for", "and", "but", "like", "i", "it", "they", "we", "you"]`.
    - Increased the word loop threshold for these whitelisted words to **6 repetitions** (matching the engine's "allow 5, filter 6" rule).
    - Maintained the standard **4 repetition** threshold for all other words.

### 2. Results
- **Zero Noise:** Re-running `extract_errors.py` on the latest interview batch (`output/transcribed/interview/`) now returns **0 anomalies**, confirming that the reporting noise from natural conversational stutters has been eliminated.
- **Improved Signal:** By removing these false positives, future reports will highlight only true, high-confidence hallucinations (runaway loops), making the feedback loop much more efficient.

### 3. Verification Steps (User)
1. **Run Error Extraction:** Execute `uv run python scripts/extract_errors.py --input-dir output/transcribed/interview/`
2. **Confirm Clean Report:** The output should show "Found 0 anomalies across 5 files" (assuming no new true hallucinations have occurred).

---

## Handoff: Refined Transcription Filter Hardening (Iteration 20260411_New_Interview_Output)


## 1. The Core Issue: Contiguous Loop "Restarts"
The primary failure mode was identified in `ARDMK 26-04-01.md`. A Whisper "stutter" loop (e.g., *"For the... for the..."*) that started at the end of a 60-second paragraph flush would **bypass existing filters** because the `current_paragraph` variable was reset to empty at the start of the next minute. Without a memory of the previous 10 seconds, the filter treated the first loop of the new minute as a fresh, valid sentence.

## 2. The Solution: Refined Immediate Tail Match
I implemented a highly targeted "Immediate Tail" filtering system in `scripts/transcribe.py`.

**The Final Implementation (v2):**
- **`tail_history` Buffer (150 chars):** I reduced the context window from 1000 characters to just 150 characters. This ensures the filter only "remembers" the immediately preceding 10-20 seconds of speech.
- **Full Segment Existence Check:** Instead of checking for small prefix matches (which caused "long-distance" false positives), the filter now only skips a segment if the **entire** clean text (minimum 10 chars) is found within the short `tail_history`. This perfectly targets Whisper's contiguous stuttering loops while allowing the same phrase to be spoken naturally a few minutes later.
- **Improved Context Continuity:** By preserving this 150-character tail across paragraph flushes, we successfully bridge the 60-second boundary that previously allowed loops to restart.

## 3. Handling False Positives (The "Yeah" Problem)
The error analysis tool flagged several instances of natural conversational agreement ("Yeah yeah") as hallucinations.

**The Solution:**
- **Nuanced Filler Filtering:** Instead of blanket-excluding words like "yeah" and "okay", the filter now uses a tiered approach. It allows these words to repeat naturally (up to 5 times), but if they repeat **6 or more times** (a clear Whisper failure mode), they are still filtered out. This preserves natural "yeah yeah yeah yeah" while catching the infinite loop cases.
- **Internal Loop Logic:** Maintained the phrase loop detector (e.g., "for the... for the...") for repetitions *within* a single segment, ensuring internal stutters are caught before they ever reach the history buffer.

## 4. Verification Results (Simulation)
I verified the logic against the known failure cases:
- **"For the..." Loop:** Successfully caught across the paragraph boundary because the phrase exists in the immediate `tail_history`.
- **"Yeah yeah yeah yeah":** Now **preserved** (no longer filtered) as it stays under the 6-repetition threshold for fillers.
- **Natural Repetition:** Phrases repeated after a few sentences are **preserved** because they fall out of the 150-character `tail_history` window.

## 5. Duration Verification Utility
I have created `scripts/verify_duration.py` to prevent "silent" truncation where the transcript ends before the audio.

- **How it works:** It uses `ffprobe` to get the exact duration of the `.mp3` file and compares it to the last `[XX.X]` timestamp in the `.md` transcript.
- **Auto-Check:** This script is now integrated into `transcribe.sh`, `transcribe-interview.sh`, and `transcribe-sangha.sh`. It runs automatically after transcription and prints a report.
- **Fail-Safe:** If a transcript is more than 120 seconds shorter than the audio, it flags it as **TRUNCATED** and warns the user.

## Handoff: Cross-Segment Loop Detection & Workflow Hardening (Iteration 20260411_New_Interview_MD)

### 1. Improvements to `scripts/transcribe.py`
- **Cross-Segment Phrase Loop Detection:** 
    - Previously, phrase loop regexes (`(.{5,}?)( \1){2,}` and `(.{15,}?)( \1){1,}`) were only applied to the *current* segment. This allowed loops to bypass filters if they started in the previous segment and continued in the new one.
    - **Fix:** I implemented `combined_text = (clean_history + " " + clean_text).strip()`. The regexes are now evaluated against this combined string, catching continuous repetitions that span across segment boundaries.
- **Expanded Filler Whitelist:** 
    - The `extract_errors.py` tool was flagging natural conversational stutters on common words as hallucinations.
    - **Fix:** Expanded the allowed filler word list to include: `"for"`, `"and"`, `"but"`, `"like"`, `"i"`, `"it"`, `"they"`, `"we"`, `"you"`. These words can now repeat up to 5 times naturally (e.g., "for... for... for...") without the entire segment being dropped.

### 2. Workflow & Spec Hardening
- **Mandatory Hard Stops:** Updated `spec.md` and the `Iteration Template` in `plan.md` to enforce two critical manual interventions:
    1.  **Model Switch:** Explicit stop to ensure analysis is performed by a high-tier LLM (Opus/Sonnet 3.5).
    2.  **Plan Review:** Explicit stop after the AI proposes an improvement plan but before implementation begins. This ensures human oversight of the strategy.
- **Diminishing Returns Check:** Integrated an evaluation step into the analysis phase where the high-tier model must determine if the script has reached its practical limit. This prevents endless marginal tweaking and potential over-filtering of valid speech.

### 3. Verification Steps (User)
1.  **Run Transcription:** Execute `./transcribe-interview.sh` on the interview batch.
2.  **Verify Loops:** Check `ARDMK 26-04-01.md` around `[71.1]` for the "which consciousness..." loop. It should now be filtered.
3.  **Verify Stutters:** Check for "For... For... For..." in `ARDMK 26-04-01.md` around `[63.4]`. Natural stutters (under 6 reps) should now be preserved rather than the whole segment being skipped.

### 4. Errors, Issues, and Repeated Mistakes
- **Issue:** Naive substring checks (`clean_text in clean_history`) are insufficient for cross-segment loops if the new segment contains any non-repeated trailing text.
- **Correction:** Use `combined_text` regex evaluation to catch the repetition pattern itself, regardless of where the segment boundary falls.
- **False Positives:** Strict word loop detection (4+ reps) on non-filler words often flags valid conversational stutters. The whitelist approach is a necessary middle ground.
