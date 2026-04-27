# Handoff: Ongoing Batch Pali Feedback Loop

## How to Use This File
Read this before every session. It records what has been attempted, what worked,
what failed, and what patterns are known — so no session repeats prior mistakes.

---

## Prompt State (as of thread creation: 2026-04-27)
Current `PALI_SYSTEM_INSTRUCTION` in `tools/pali.py` has 11 rules. All rules
below are already implemented and must NOT be re-proposed.

### Rules Already Implemented
1. Analyze for phonetic/semantic Pali misspellings against glossary
2. Strict context check — only correct if Buddhist context is clear
3. Capitalization awareness — suspicious of capitalized English names
4. Ignore ALL-CAPS acronyms unless in glossary
5. Multi-word bridging — identify two/three-word sequences that form one Pali term
   (e.g., `Viragadham Mikam` → `Virāgadhammikaṁ`)
6. Consistency — once a correction is found, scan for phonetic variants of same term
7. Semantic hallucinations — "Deep Hallucination" examples:
   - `Norway for far` → `Noble Eightfold Path`
   - `Marginal Triad` → `Majjhima Nikāya`
   - `put up` → `patta`
   - `Logan needed` → `lokavidū`
   - `the ergonomic big group` → `the Virāgadhammika Bhikkhu`
   - `share the down` → `share the Dhamma`
8. Monastic names & titles — phonetic correction + shortened name expansion
   (e.g., `Virāga` → `Virāgadhammika`)
9. Output ONLY a valid JSON array with `original` and `corrected` keys
10. English Buddhist terms — phonetic mistranslations of common English words
    (e.g., `senior moms` → `senior monks`, `non` → `nun`)
11. Extreme phonetic distortions — foreign place names severely mangled
    (e.g., `Waddenwood-Pupon` → `Wat Nong Pah Pong`)

---

## Known Patterns (from prior sessions on correct_pali.py)
These patterns are confirmed real and should be watched for in batch output:

- **Creative Hallucinations:** Whisper "translates" complex Pali/monastery names
  into plausible English nonsense (e.g., `Sunripe` for `Sasanarakkha`)
- **Title Merging:** Monastic titles and names fuse into phonetic garbles
  (e.g., `Bandiaga Jitta` → `Bhante Aggacitta`)
- **Capitalization Bias:** STT software capitalizes Pali words as if they were
  proper English nouns — already handled in Rule 3
- **Hyphenated Terms:** `\b` word-boundary regex handles hyphenated garbles
  correctly as long as the LLM returns the exact original string

---

## Errors & Repeated Mistakes to Avoid
- **REDUNDANT RE-RUNS (CRITICAL WASTE):** Never delete successful corrected output
  to re-run a "clean" batch. If output is correct, keep it. Economy mandate.
- **Verification delay:** Corrected files may appear unchanged if inspected before
  the script finishes writing. Always confirm the process has fully exited first.
- **Glossary.py is out of scope here:** Vocabulary additions go in the
  `ongoing_pali_correction_feedback` thread, not this one.

---

## Session Log

### 2026-04-27 (Current Session)
**Context:** Batch output from `output/corrected_pali/interview/` (OpenAI Batch).
**Anomalies Found:**
- **Hallucinations (Wrong Pali):** LLM favoring complex Sanskrit-sounding terms over common Theravada Pali.
  - `India Asambara` / `India Samara` -> `India Āsambhava` (Should be `Indriya Saṃvara`)
  - `Abiyapadjadimupta` -> `Abhijjhadhamma` (Should be `Abyāpajjādhimutta`)
  - `samiltonica` -> `sāmantabhadra` (Should be `Saṃyutta Nikāya`)
- **Missed Corrections (English Conjunctions):** LLM failed to bridge common English words that refer to single Pali terms.
  - `Brahma and hara` -> `Brahma and hara` (Should be `Brahmavihāra`)
  - `Tsutajana` -> `Tsutajana` (Should be `Sutta-jhāna`)

**Changes Implemented:**
- **tools/glossary.py:** Added `# 7. Common Sutta Terms` section with 13 new terms (including `Indriya Saṃvara`, `Abyāpajjādhimutta`, `Sutta-jhāna`).
- **tools/pali.py (Prompt):**
  - **Rule 7:** Expanded to include "ENGLISH CONJUNCTIONS" with `Brahma and hara` example.
  - **Rule 12 (New):** "THERAVADA PALI BIAS" — explicitly forbids complex/Sanskrit over-corrections and mandates glossary priority.

**Errors or Repeated Mistakes:**
- `evaluate_pali.py` (Rule-based) found 0 anomalies because character/word count changes were below threshold. **Manual diffing (mental or tool-assisted) is still required to catch semantic hallucinations.**
- Ensure `_combined` in `tools/pali.py` imports all relevant sections from `tools/glossary.py`.
