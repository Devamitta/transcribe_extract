# Handoff: Ongoing Semantic Evaluation Loop

## Session log

### Session 1: 2026-04-28 — Batch evaluation mode, Phase 1–3 complete

- **last_run:** 2026-04-28T05:59:32Z
- **Date:** April 28, 2026
- **Evaluation mode:** Batch (`scripts/batch.py --stage semantic --folder interview`)
- **Files processed:** 4 files with findings + 1 file with no anomalies
  - Ardmk 22-03-09.md
  - Ardmk 22-03-20patimokkha + dhammadesana.md
  - Ardmk 22-03-26.md
  - Ardmk 22-04-04.md
- **Fixes applied:** 8 high-confidence replacements
  1. "chuck" → "cakkhu" (File 1)
  2. "Nigger Heater" → "Niggahīta" (File 2)
  3. "in teams" → "in temples" ×2 occurrences (File 2)
  4. "boobies" → "Buddhists" (File 2)
  5. "be my kind" → "mind doing" (File 2)
  6. "may may" → "may" (File 4)
  7. "chimes" → "themes" (File 5)
  8. "teeth" → "deaf" (File 5)
- **Deferred findings:** 17 true positives with uncertain replacements (garbled Pali terms, garbled bhikkhu names, Pāṭimokkha chanting phrases) — require user knowledge for correct form
- **Prompt improvements:** Added to `tools/pali.py:get_semantic_eval_instruction()`:
  - Clarified DO NOT FLAG patterns: informal conversational speech, spoken English grammar, valid Pali terms in study context, valid doctrinal statements
  - Added DO FLAG patterns: offensive word substitutions (HIGH PRIORITY), English phonetic confusions, Pāṭimokkha chanting garbles
  - Strengthened CRITICAL RULE on exact passage citation
- **Issues encountered:** None; report format was clean and structured

### Phase 3b: User collaboration on deferred findings

- **Identified with user:** 4 additional corrections through manual context review
  1. "lapidamnete" → "Monk Training Center" (File 1) [1 replacement]
  2. "Ganyanka" → "Goenka" (File 4) [2 replacements]
  3. "Venerable Raffole" → "Venerable Rahula" (File 5) [1 replacement]
  4. "right life fluid" → "right livelihood" (File 5) [3 replacements]
  - **Total:** 7 replacements applied
- **Skipped as irrelevant:** Banditama bhikkhu, Abitava, Tamabudu (File 1); Equd desu, Tanthavaye, Hichivaram (File 2); Indodakshu (File 4)
- **Total session output:** 12 high-confidence fixes applied + 4 additional user-identified fixes = **16 total replacements**

## Errors, issues, and repeated mistakes
_None yet. When sessions occur, append findings here: what caused delays, what unclear instructions were, model-specific issues, unexpected report formats, etc._
