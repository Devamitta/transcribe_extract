# Handoff: Ongoing Pali Correction Feedback Loop

## Latest Status: Iteration 4 (Sangha Batch) - COMPLETED
The prompt hardening for the `sangha` batch is fully implemented in `scripts/correct_pali.py`.
- **Implemented:** Multi-Word Bridging (e.g., `Viragadham Mikam` → `Virāgadhammikaṁ`).
- **Implemented:** Contextual Consistency (Mandatory scan for phonetic variants within a chunk).
- **Implemented:** New Deep Hallucination examples (`put up`, `the ergonomic big group`).
- **Updated:** `tools/glossary.py` now includes `lokavidū`.

---

## Cumulative System Improvements

### 1. Architecture & Infrastructure (Implemented)
- **Structural JSON Fix:** The LLM now only outputs a JSON array of `original:corrected` pairs. Python applies these via regex word boundaries, eliminating structural anomalies and infinite loops.
- **Robust Resume Logic:** JSON-based `.status` tracking prevents corruption and allows safe resumption of long processing tasks.
- **Validation:** Strict verification that LLM output contains both 'original' and 'corrected' keys before application.

### 2. Hardened Prompt Rules (Implemented)
- **Multi-Word Bridging (New):** Explicitly handles cases where Whisper inserts spaces into the middle of Pali words.
- **Consistency Rule (New):** Mandates that once a correction is identified, all similar phonetic variants in the chunk must be corrected.
- **Semantic Guardrails:** "Deep Hallucination" detection for complex phrases (e.g., "Norway for far" -> "Noble Eightfold Path").
- **Capitalization Awareness:** Instructions to be suspicious of capitalized English names (e.g., "Sutter" -> "sutta") while ignoring non-glossary acronyms.
- **Monastic Name Logic:** Specific rules for phonetic title correction and automatic expansion of shortened names (e.g., `Virāga` → `Virāgadhammika`).

### 3. Glossary Expansion (`tools/glossary.py`)
- **Saṅgha/Places:** Added `Wat Nong Pah Pong`, `Sasanarakkha`, `Luddhara`, `Amaravati`.
- **Monastics:** Full Pāli names from Sasanarakkha integrated.
- **Dhamma:** Added `lokavidū`, `Abhidhamma`, and semantic English-Pali pairs.

---

## Critical Findings & Patterns (Lessons Learned)
- **Creative Hallucinations:** Whisper "translates" complex terms into nonsense English (e.g., `Sunripe` for `Sasanarakkha`).
- **Title Merging:** Monastic titles and names often merge into single phonetic garbles.
- **Capitalization Bias:** Transcription software often capitalizes Pali words by mistake, which the prompt now successfully detects and fixes.

---

## Final Verification Steps
1. User should clear `.status` for the `sangha` batch: `rm -rf output/corrected_pali/sangha/.status/`.
2. Run the updated script: `uv run python scripts/correct_pali.py sangha`.
3. Verify that previously missed terms (e.g., `put up`, `Logan needed`, `Ergadamica`) are now correctly caught.

---

## Update: 2026-04-24 - Iteration 1 (Sangha Meeting Batch)
The loop was restarted on a new batch of Sangha meeting transcripts (Part I & II).

### Implemented Improvements
- **Rule 10 (ENGLISH BUDDHIST TERMS):** Added to catch phonetic mistranslations of common English words that are not in the Pali glossary but are contextually important (e.g., "senior moms" -> "senior monks", "non" -> "nun").
- **Rule 11 (EXTREME PHONETIC DISTORTIONS):** Added to specifically target heavily mangled Thai place names (e.g., "Waddenwood-Pupon" -> "Wat Nong Pah Pong").
- **Expanded Semantic Hallucinations:** Added "share the down" -> "share the Dhamma" to Rule 7.

### Errors, Issues, and Repeated Mistakes
- **Redundant Processing (CRITICAL WASTE):** Deleting successful LLM output to re-run a "clean" batch is a violation of the economy mandate. During Iteration 1, work was successfully completed for one file, then deleted and re-run for the whole folder unnecessarily. **DO NOT delete successful output to re-verify; if it's correct, keep it.**
- **Missed Corrections (Initial):** The prompt originally missed "Wat Nong Pah Pong" and "Dhamma" mishearings because they were too phonetically distant or involved English words rather than Pali.
- **Regex Word Boundaries:** A hyphenated term like "Waddenwood-Pupon" was confirmed to be correctly handled by the `\b` word boundary regex in Python, provided the LLM returns the exact string.
- **Verification Delay:** During verification, the corrected file appeared unchanged if checked before the script fully finalized its write operation. Always ensure the script has finished and saved before inspecting results.

### Next Steps
- Monitor the current batch for any new phonetic hallucinations of Bhante names or specific Sangha terms.
- Iteration 1 is verified; the thread is ready for review or the next batch of audio.
