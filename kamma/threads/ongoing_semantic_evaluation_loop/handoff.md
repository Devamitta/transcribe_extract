# Handoff: Ongoing Semantic Evaluation Loop

## How to Use This File
Read this before every session. It records what has been attempted, what worked,
what failed, and what patterns are known — so no session repeats prior mistakes.

All archived sessions are in this thread folder `archive/handoff_archive.md`. Only the 2 most recent sessions are kept in this file for quick reference.

---

## ⚠️ EVERY SESSION END — Handoff Maintenance Checklist

**Before marking the session complete, run these steps:**

- Move session [N-2] from this file to `archive/handoff_archive.md` (keep only sessions [N-1, N])
- Delete old session entries from "Errors, issues, and repeated mistakes" section
- Verify this file contains ONLY the 2 most recent sessions + their errors
- Verify `archive/handoff_archive.md` received the archived session
- Confirm `plan.md` is unchanged (reusable template for next session)

**If you skip this, the next session's handoff will be 100+ lines too long. Don't skip.**

---

## Session log

### Session 9: 2026-04-29 — Phase 1–3 complete, 21 confident fixes + 16 deferred terms

- **last_run:** 2026-04-29T23:59:59Z
- **Date:** 2026-04-29
- **Evaluation mode:** Batch (fresh reports from pending queue)
- **Files processed:** 10 fresh reports from pending_next_session
  - All 10 with findings: 138 total findings (79% false positives, consistent with Session 8)
- **Classification summary:**
  - True positives (confident fixes): 21
  - True positives (deferred_dhamma): 16
  - False positives: 101 (informal_speech, grammar, valid_content, teaching_example, context_only)
- **Fixes applied:** 21 confident fixes (28 total replacements across 9 corrected_pali files)
- **Deferred findings:** 16 items appended to manual_corrections.md (Session 9 section)
- **Prompt improvements applied:** 2 additions to `get_semantic_eval_instruction()` in tools/pali.py
  - DO NOT FLAG: Valid Theravada doctrinal compound terms (pītisukha, Sutta-jhāna, domanassa, kammaṭṭhāna, cakkhu-indriya)
  - KNOWN ERROR PATTERNS: 8 new Session 9 patterns (Chandra/chanda, indriya, etc.)
- **Findings skipped:** 101 false positives (informal_speech, grammar, valid_content, teaching_example, context_only)
- **Issues encountered:** None critical. Session 8 fixes confirmed applied.
- **Pending:** 11 reports remain for next session (SESSION_LIMIT capped at 10 per run)

### Session 10: 2026-04-29 — Phase 1–3 complete, 53 confident fixes + 23 deferred terms

- **last_run:** 2026-04-29T23:59:59Z (Current session)
- **Date:** 2026-04-29
- **Evaluation mode:** Batch (fresh reports from pending queue)
- **Files processed:** 10 fresh reports from pending_next_session
  - All 10 with findings: 154 total findings
  - Ardmk 22-22-04, 23-01-07, 22-12-31, 22-11-15-2, 22-07-06, 22-12-10, 22-11-05, 22-10-29, 22-11-26, 22-11-15-1
- **Classification summary:**
  - True positives (confident fixes): 53
  - True positives (deferred_dhamma): 23
  - False positives: 78 (informal_speech, valid_content, teaching_example, software_references)
- **Fixes applied:** 53 confident replacements across 10 files.
  - Highlights: "Asitta Bari word" → "Asitta Bari, which", "anti-dex" → "Anki decks", "Wapan Manachai" → "Wat Pa Nanachat", "chivalry" → "cīvara".
- **Deferred findings:** 23 items appended to manual_corrections.md (Session 10 section).
- **Prompt improvements applied:** 2 additions to `get_semantic_eval_instruction()` in tools/pali.py
  - DO NOT FLAG: Informal fillers ("it's like", "sort of") and mechanical repetitions.
  - DO NOT FLAG: Common software tools (Anki, GoldenDict).
  - KNOWN ERROR PATTERNS: 25 new Session 10 patterns.
- **Findings skipped:** 78 false positives (valid analogies like "bitcoin lifestyle", oral repetitions).
- **Issues encountered:** None. High volume of fixes (5.3 per file) indicates evaluator catching many phonetic garbles previously missed.
- **Pending:** 9 reports remain for next session (SESSION_LIMIT capped at 10 per run).

**Errors, issues, and repeated mistakes:**
- **Consistent false positive rate:** ~50% in this session (lower than 79% in prior sessions), likely due to Session 9 prompt improvements and clearer true positives.
- **Phonetic garbles of names/places:** Whisper continues to struggle with "Wat Pa Nanachat" and "Ajahn Brahm" (garbled as "Wapan Manachai" and "Sgt. Brahms"). Added to prompt.
- **Software tools:** Evaluator flagged "Anki" and "GoldenDict" as errors; added to DO NOT FLAG list.
- **Informal speech:** Many false positives were just oral stuttering or fillers; added explicit instruction to ignore.
