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

### 2026-04-27 (Session 2)
**Context:** Manual evaluation of `output/corrected_pali/interview/` batch output.
**Anomalies Found:**
- **Hallucinations (Glossary Fallback):** `India Asambara` -> `India Aṅguttara`, `Upasmanus` -> `Upāsakā`. Root cause identified as missing glossary terms causing model to settle for the closest available phonetic match.
- **Missed Corrections:** `Filabata, Paramahasa` (Sīlabbata-parāmāsa), `Jaraa Monkhi` (Jarā-maraṇa), `Sasankara Migaiha Varita Gatan` (Sasaṅkhāraniggahavāritavata).
- **Compound Failure:** `gpt-4o-mini` struggles to reconstruct complex multi-word Pali compounds without an exact glossary match.

**Changes Implemented:**
- **tools/glossary.py:** Added one-word compounds to `# 7. Common Sutta Terms` (`Indriyasaṃvara`, `Upasamanussati`, `Sīlabbataparāmāsa`, `Jarāmaraṇa`, `Sasaṅkhāraniggahavāritavata`).
- **tools/pali.py (Prompt):**
  - **Rule 12:** Updated example to use the one-word compound `Indriyasaṃvara`.

**Errors or Repeated Mistakes:**
- The "Diminishing Returns Principle" was invoked: prompt engineering alone cannot solve phonetic garbles for terms missing from the glossary.
- **Strategic pivot:** We broke the "Glossary.py is out of scope" rule for this thread to test the hypothesis that one-word compounds in the glossary improve `gpt-4o-mini` performance on complex terms.

### 2026-04-27 (Session 3)
**Context:** Evaluation of `output/corrected_pali/interview/` (gpt-4o-mini).
**Anomalies Found:**
- **CRITICAL: Meaning Flip Hallucinations:** The model is "correcting" Pali garbles into words that sound similar but have the opposite meaning.
  - `papañca` (proliferation) -> `Paññā` (wisdom). This is disastrous for Buddhist text integrity.
  - `anayutham` (not striving) -> `anuyoga` (striving/devotion).
- **Aggressive Over-Correction:** Proper names and English phrases are being forced into Pali glossary terms.
  - `bodiless addiction` (Bhikkhu Bodhi) -> `Brahmacariya`.
  - `Baog` (Pa-Auk) -> `bhavanga`.
- **Glossary Failures:** Missing glossary terms for `vossagga-pariṇāmiṁ` and `ākiñcaññāyatana` led to invented phonetic compounds.

**Changes Implemented:**
- **No Prompt Changes:** We have reached the limits of `gpt-4o-mini`. Further prompt engineering is likely to cause "whack-a-mole" regressions.
- **Data Preservation:** Moved `gpt-4o-mini` output to `output/corrected_pali/interview/gpt-4o-mini/` for benchmarking.

**Errors or Repeated Mistakes:**
- `gpt-4o-mini` is too "eager" and lacks the reasoning depth to apply Rule 2 (Strict Context Check) effectively.
- **Strategy Pivot:** Concluding the iterative prompt-tweaking loop. Moving to a **Model Comparison Phase** to find a model capable of handling phonetic reconstruction without semantic destruction.

### 2026-04-27 (Session 4)
**Context:** Comparison of `gpt-4o-mini` vs `gpt-5-mini` on `output/corrected_pali/interview/`.
**Comparison Results:**
- **Hallucination Fix:** `gpt-5-mini` correctly identified `Indriyasaṃvara` (garbled as `India Asambara`) whereas `gpt-4o-mini` previously hallucinated `India Āsambhava`.
- **Aggressive Over-correction (Regression in 4o-mini):** `gpt-4o-mini` was found to be "Buddhicizing" the text by replacing common English words (`mind` -> `citta`, `meditation` -> `bhāvanā`, `project` -> `puñña`) even when they were clearly spoken in English.
- **Faithfulness:** `gpt-5-mini` is significantly more faithful to the original English terminology while still applying correct Pali diacritics and phonetic fixes.
- **Automated Metrics:** Both models returned 0 anomalies in `evaluate_pali.py`, confirming the script's inability to detect semantic over-corrections.

**Strategic Recommendation:**
- **Stick with gpt-5-mini:** It clearly possesses the reasoning depth to distinguish between "garbled Pali that needs fixing" and "valid English that should be left alone."
- **Prompt Maintenance:** No changes to `PALI_SYSTEM_INSTRUCTION` are needed at this time as the model switch solved the primary issues identified in Session 3.
- **Conclusion:** The iterative prompt-tweaking loop for this batch is concluded. `gpt-5-mini` is the approved model for this pipeline.

### 2026-04-27 (Session 5)
**Context:** Manual evaluation of `output/corrected_pali/interview/` (gpt-5-mini).
**Anomalies Found:**
- **English Word Overrides:** gpt-5-mini missed several instances where common English words were forced onto Pali terms.
  - `genre` / `genres` / `Janna` -> `jhāna`
  - `false janas` -> `fourth jhāna`
  - `Europa` -> `arūpa`
  - `hook-up` -> `bhikkhu`
- **Acronym Phonetic Garbles:** `S-Base` -> `SBS`.
- **Missing Glossary Terms:** `Fagicates` -> `five aggregates`, `Manku Bhutam` -> `maṅku-bhūta`.

**Changes Implemented:**
- **tools/glossary.py:** Added `five aggregates` and `maṅku-bhūta` to `EXTENDED_TERMS`.
- **tools/pali.py (Prompt):**
  - **Rule 4:** Expanded to include phonetic garbles of glossary acronyms (e.g., `S-Base` -> `SBS`).
  - **Rule 10:** Expanded to include "OVERRIDES" where unrelated English words are forced onto Pali terms, with several specific examples (`genre`, `Europa`, `hook-up`).

**Errors or Repeated Mistakes:**
- Automated metrics in `evaluate_pali.py` continue to report 0 anomalies because they primarily track character/word count changes, not semantic accuracy. Manual spot-checking is essential.
- gpt-5-mini is a significant improvement over 4o-mini but still requires specific "override" examples in the prompt to avoid being too faithful to phonetic English misspellings.

### 2026-04-27 (Session 6)
**Context:** Manual evaluation of `output/corrected_pali/interview/` (gpt-5-mini).
**Anomalies Found:**
- **"Meaning Flip" Hallucinations:** gpt-5-mini replaced less common but phonetically accurate terms with more common ones (e.g., `Potapa` -> `vedanā` instead of `phoṭṭhabba`).
- **Missed English Overrides (Deep Hallucinations):** `five-year-old` (five aggregates) and `wire tomorrow` (vaya-dhamma) were missed.
- **Missed Sutta Phrases:** Complex phrases like `parimukhaṃ satiṃ upaṭṭhapetvā` (garbled as `Satin-Varibhung-Kang-Battapetva`) and `sato va assasati` were missed.
- **Missed Monastic Variant:** `Pandiakuchit` (Bhante Aggacitta).

**Changes Implemented:**
- **tools/glossary.py:** Added core Dhamma terms (`phoṭṭhabba`, `phassa`, `vaya-dhamma`, `nāmarūpa`) and Sutta phrases (`sabbakāya`, `parimukhaṃ satiṃ upaṭṭhapetvā`, `sato va assasati sato va passasati`, `Dhammadesanā`).
- **tools/pali.py (Prompt):**
  - **Rule 5:** Added extreme Sutta garble example (`parimukhaṃ satiṃ upaṭṭhapetvā`).
  - **Rule 7:** Added `five-year-old` and `wire tomorrow` as deep hallucination examples.
  - **Rule 10:** Added `Potapa` -> `phoṭṭhabba` and explicitly forbid replacing less common terms with more common ones if the phonetic match is strong.

**Errors or Repeated Mistakes:**
- Automated metrics in `evaluate_pali.py` still report 0 anomalies. Manual diffing remains the primary tool for semantic quality control.
- `gpt-5-mini` is much better than `4o-mini` but still prone to "Buddhicizing" by choosing the most frequent Pali terms over the most phonetically accurate ones.

### 2026-04-27 (Session 7)
**Context:** Manual evaluation of `output/corrected_pali/interview/` (gpt-5-mini).
**Anomalies Found:**
- **Hallucinations (Monastic Over-correction):** `pāmojja` (joy) was corrected to `Pamodadhammika` (monastic name). Root cause: the "SHORTENED NAMES" rule was too aggressive, forcing corrections to `-dhammika` names.
- **Missed Deep Hallucinations:** `much money car` -> `Majjhima Nikāya` was missed.
- **Missed Sutta Phrases (MN 118):** Several core phrases and terms from the Anapanasati Sutta were missed or partially corrected (`pajānāti`, `sabbakāya-paṭisaṃvedī`, `assasati`, `passasati`, `dīgha`, `rassa`).
- **Missed Terms:** `Aṅguttara` (as `Anbuddhra`), `Kaṭhina`.

**Changes Implemented:**
- **tools/pali.py (Prompt):**
  - **Rule 7:** Added \`much money car\` -> \`Majjhima Nikāya\` example.
  - **Rule 8:** Removed the "SHORTENED NAMES" instruction to prevent over-correction of common Pali words to monastic names.
- **tools/glossary.py:**
  - **EXTENDED_TERMS:** Added \`Aṅguttara\`.
  - **SUTTA_TERMS:** Added \`pāmojja\`, \`kāyasaṅkhāra\`, \`pajānāti\`, \`sabbakāya-paṭisaṃvedī\`, \`assasati\`, \`passasati\`, \`dīgha\`, \`rassa\`.
- **spec.md:** Added a CRITICAL GLOSSARY RULE forbidding modification of DHAMMA, SANGHA, or VINAYA categories.
- **Manual Data Correction:** Ran \`temp/apply_fixes.py\` to directly apply these corrections to 7 files in \`output/corrected_pali/interview/\`, preserving the existing batch output while fixing the identified hallucinations.

**Errors or Repeated Mistakes:**

- The automated evaluation script (`evaluate_pali.py`) continues to report 0 anomalies for semantic issues, making manual diffing the only reliable way to catch "meaning flip" or "monastic over-correction" hallucinations.

### 2026-04-27 (Session 8)
**Context:** Manual evaluation and folder-aware prompt refactoring for `output/corrected_pali/interview/`.
**Anomalies Found:**
- **CRITICAL: Monastic Over-correction:** `pāmojja` and `abhipāmojja` were aggressively replaced by `Pamodadhammika` in interview files where monastic names are out of context.
- **Missed Famous Teachers:** `Goenka`, `Ajahn Thanissaro`, `Pa-Auk Sayadaw`, `Bhikkhu Anālayo`, `Bhikkhu Bodhi`, `Bhikkhu Sujato` were mangled/missed.
- **Missed Sutta Phrases:** `Cūḷavedalla Sutta`, `Visuddhimagga`, `kaṭhina-māsa`, `passambhayaṃ`, `sabbakāya`.

**Changes Implemented:**
- **tools/glossary.py:** Added `FAMOUS_TEACHERS` list and expanded `SUTTA_TERMS`.
- **tools/pali.py:** Refactored `PALI_SYSTEM_INSTRUCTION` into `get_pali_system_instruction(file_path)`. Implemented dynamic glossary: excludes `MONASTICS` if the file path is not in a 'sangha' folder.
- **scripts/batch.py:** Updated to fetch folder-aware instructions per file.
- **scripts/correct_pali.py:** Updated to fetch folder-aware instructions per file.
- **Manual Data Correction:** Ran `temp/apply_fixes.py` to revert hallucinations in 7 interview files.

**Errors or Repeated Mistakes:**
- The automated evaluation script (`evaluate_pali.py`) remains unable to catch these semantic "meaning flips." Manual spot-checking is required until a more sophisticated evaluation script is developed.
- **Conclusion:** Structurally solved the monastic over-correction issue by making the glossary folder-aware.

### 2026-04-27 (Session 9)
**Context:** Comprehensive manual spot-check of all 45 interview files.
**Anomalies Found:**
- **CRITICAL Meaning Flip Hallucinations:** 'vagina/vaginas' (paññā), 'red cock noise' (recognition), 'winner' (Vinaya), 'epidemic' (Abhidhamma), 'terrible school' (Theravāda school), 'Russian canon' (Theravāda canon), 'I cook' (Ariyadhammika).
- **Missed Phonetic Garbles:** 'Fittincau' (viññāṇa), 'Bodhisattva' (vedanā), 'Ichi' (saṅkhāra), 'Namopar' (nāmarūpa), 'Dhakkhan' (vitakka), 'Siddhippa Tano' (satipaṭṭhāna), 'Patisandrila Mnana' (Paṭisambhidāmagga).
- **Missed Proper Names:** 'Richard Goldbich' (Richard Gombrich), 'devil meter' (Devamitta), 'German' (Ñāṇadhammika).

**Changes Implemented:**
- **plan.md:** Updated Task X.1 to mandate a comprehensive manual 'grep' sweep across all files, as automated evaluation misses semantic hallucinations.
- **tools/glossary.py:** Added 'Richard Gombrich' to FAMOUS_TEACHERS and 'Pa-Auk' to EXTENDED_TERMS.
- **tools/pali.py (Prompt):**
  - **Rule 7:** Added 'epidemic' -> 'Abhidhamma' example.
  - **Rule 10:** Added overrides for 'vagina', 'winner', and 'red cock noise'.
  - **Rule 11:** Added phonetic distortion examples for 'Fittincau' and 'Bauch' -> 'Pa-Auk'.
- **Manual Data Correction:** Ran 'temp/apply_fixes.py' to patch 32 files in 'output/corrected_pali/interview/' with the correct terms.

**Errors or Repeated Mistakes:**
- Automated evaluation script remains ineffective for semantic errors. 
- Manual patching is the only way to avoid re-running expensive LLM batches for known hallucinations.

---

## Session Log

### 2026-04-27 (Session 10)
**Context:** Manual evaluation of `output/corrected_pali/interview/ARDMK 26-04-01.md` (latest batch).
**Anomalies Found:**
- **CRITICAL Meaning Flip Hallucinations:** 'polyvots' (body parts), 'fire fire rivers' (five aggregates), 'super-cold' / 'super-ganda' (upādānakkhandha), 'sliver' (saliva), 'global group' (noble eightfold path), 'civilization' (volition), 'minerals' (monastics), 'the singer' (the Sangha).
- **Missed Phonetic Garbles:** 'Mosaik put' (Sāriputta), 'points to dance' (phoṭṭhabba), 'jayetana' (cetanā), 'ten in us' (cetanā), 'Hupa Kalapa' (rūpa kalāpa), 'proper pancha' (papañca), 'he was sicko' (ehipassiko), 'Vyana-beta' (viññāṇapeta).
- **Proper Names:** 'Pomola' (Pāmojja), 'Gammaji' (Dhammajī), 'Genesiri' (Jinasiri), 'Bayon Katie' (Byron Katie), 'Yostovicia' (euthanasia).

**Changes Implemented:**
- **tools/glossary.py:** Added missing Pāli terms (`upādānakkhandha`, `cetanā`, `rūpa kalāpa`, `papañca`, `paccaya`, `ehipassiko`, `viññāṇapeta`, `saññā vedayita nirodha`, `puñña`, `apuñña`, `āneñja`) and teachers (`Byron Katie`, `Sāti`, `Dhammajī`, `Jinasiri`).
- **tools/pali.py (Prompt):**
  - **Rule 7:** Added examples for 'Majjhima Nikāya', 'ceases and another has arisen', 'papañca', 'saññā disappeared', and 'noble eightfold path'.
  - **Rule 8:** Added monastic title/name mappings for 'Bhante', 'Dhammajī', and 'Jinasiri'.
  - **Rule 10:** Added 20+ new "OVERRIDE" examples covering semantic hallucinations found in Session 10.
- **Manual Data Correction:** Manually patched `output/corrected_pali/interview/ARDMK 26-04-01.md` with correct terms.

**Errors or Repeated Mistakes:**
- The prompt is becoming quite large due to Rule 10 examples. If performance degrades, consider moving these examples into a separate JSON lookup or "Few-Shot" file.
- **Strategic Note:** The "Economy" mandate was strictly followed; we manually patched the data rather than re-running the entire batch.
