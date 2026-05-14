# Handoff: Ongoing Semantic Evaluation Loop

## How to Use This File
Read this before every session. It records what has been attempted, what worked,
what failed, and what patterns are known — so no session repeats prior mistakes.

All archived sessions are in this thread folder `archive/handoff_archive.md`. Only the 2 most recent sessions are kept in this file for quick reference.

---

## ⚠️ EVERY SESSION END — Handoff Maintenance Checklist

**Before marking the session complete, run these steps:**

- Move session [N-2] from this file to `archive/handoff_archive.md` (keep only sessions [N-1, N])
- Archive Session [N-2] from `manual_corrections.md` to `archive/manual_corrections_archive.md`
- Update "Hot List" in `manual_corrections.md` with current unresolved items
- Prune `ledger.json` (remove entries older than 2 sessions or marked "clean")
- Delete old session entries from "Errors, issues, and repeated mistakes" section
- Verify this file contains ONLY the 2 most recent sessions + their errors
- Verify `archive/handoff_archive.md` received the archived session
- Confirm `plan.md` is unchanged (reusable template for next session)

**If you skip this, the next session's handoff will be 100+ lines too long. Don't skip.**

---

## Session log

### Session 17: 2026-04-30 — Phase 1–3 complete, 29 fixes applied + 18 deferred items

- **last_run:** 2026-04-30T13:10:00Z
- **Date:** 2026-04-30
- **Evaluation mode:** Batch (fresh reports from pending queue)
- **Files processed:** 10 fresh reports
  - Clean: 0
  - With findings: 10 (Ardmk 24-02-26 to 24-01-13)
  - Total findings analyzed: 138
- **Classification summary:**
  - True positives (confident fixes): 29
  - True positives (deferred_dhamma): 18
  - False positives: 91 (informal_speech, vivid metaphors, grammar, historically valid suicide refs)
- **Fixes applied:** 29 replacements across 9 files.
  - Highlights: "integrated in their normal manata" → "integrated in their normal mānatta", "sudden funny" → "sudden paññā", "destruction of the Danes" → "destruction of the taints".
- **Deferred findings:** 18 items appended to manual_corrections.md (Session 17 section).
- **Prompt improvements applied:** Added 3 new patterns and 3 new 'DO NOT FLAG' rules.
  - DO NOT FLAG: Historical suicide refs (Godhika, Channa), Microsoft Teams refs, Valid but slightly off Pali spellings.
  - KNOWN ERROR PATTERNS: Vajitya, comedies, sudden funny, basic zhila, etc.
- **Findings skipped:** 91 false positives.
- **Issues encountered:** Multiple "in teams" substitutions in doctrinal context correctly flagged (should be "in temples" or "in terms"). Added specific Teams rules.
- **Pending:** ~93 reports remain for next session.

### Session 18: 2026-04-30 — Phase 1–3 complete, 49 fixes applied + 29 deferred items

- **last_run:** 2026-04-30T17:30:00Z
- **Date:** 2026-04-30
- **Evaluation mode:** Batch (fresh reports from pending queue)
- **Files processed:** 10 fresh reports
  - Clean: 0
  - With findings: 10
  - Total findings analyzed: 128
- **Classification summary:**
  - True positives (confident fixes): 49
  - True positives (deferred_dhamma): 29
  - False positives: 50 (informal_speech, vivid metaphors, grammar)
- **Fixes applied:** 49 replacements across 10 files.
  - Highlights: "Ragado Samocha" → "rāga dosa moha", "Janus" -> "jhānas", "Banchu, Badana, Kanta" -> "pañcupādānakkhandhā".
- **Deferred findings:** 29 items appended to manual_corrections.md (Session 18 section).
- **Prompt improvements applied:** 16 new patterns and 2 new 'DO NOT FLAG' rules added to `tools/pali.py`.
  - DO NOT FLAG: Characteristically casual English grammar, Vivid teaching analogies (e.g. Russian girls, intercourse).
  - KNOWN ERROR PATTERNS: Ragado Samocha, Hamanah, world-instryment, Khochangas, vineyards, etc.
- **Findings skipped:** 50 false positives.
- **Issues encountered:** "china" confirmed as garble for "chanda"/"citta". "in teams" (temples) and "dog" (Dhamma) remain high-frequency phonetic swaps.
- **Pending:** 83 reports remain for next session.

**Errors, issues, and repeated mistakes (Session 17):**
- **Historically Valid References:** Evaluator flagged references to monks taking their lives. Added to DO NOT FLAG as these are legitimate Sutta references (Godhika, Channa).
- **Teams vs Temples:** "in teams" is a common substitution for "in temples" or "in terms", but can also be valid if discussing software. Added contextual rules.
- **Pali compounds in garbles:** "viniana, plasna, marupa" identified as "viññāṇa, phassa, nāmarūpa".

**Errors, issues, and repeated mistakes (Session 18):**
- **Vivid Analogies:** Evaluator flagged "intercourse with his wife" and "Russian girls" as awkward/wrong, but they are valid (if blunt) teaching examples in context. Expanded DO NOT FLAG to protect vivid pedagogical imagery.
- **Garbled Compound Identification:** "Banchu, Badana, Kanta" correctly identified as "pañcupādānakkhandhā" (five clinging aggregates) based on syllable counts and phonetic overlap.
- **Persistent Teams Swap:** "in teams" (temples) continues to be the most frequent phonetic swap.
