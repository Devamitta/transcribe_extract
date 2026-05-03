# Extract Quality Improvement — Handoff

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

### Session 8 — 2026-04-28 (fast→pro→fast model) — Headline Extraction Fix

**Files evaluated (post-Session 7 changes):**
- `Ardmk 22-03-09.md` (extracted) — 5,074 words vs 10,141 source (50.0%)
- `Ardmk 22-03-23.md` (extracted) — 11,544 words vs 13,364 source (86.4%)

**Assessment:**
- Session 7 improvement to 22-03-23 holds (71.6% → 86.4%) ✓
- Session 7 regression to 22-03-09 identified: 78.3% → 50.0% (significant content loss) ⚠
- Root cause: After Session 7 flexible-tag change, model creates 38 thin sections (~134 words avg) instead of full exchanges — **"headline extraction" problem**
- 22-03-09 has dense teaching topics that shift frequently; model treats each topic as a "headline" and moves to next tag
- 22-03-23 has long rambling discussions; model preserves them verbatim (no headline effect)

**Problems identified:**
1. Over-fragmentation with thin sections: 38 tagged sections in 22-03-09 (should be 10-20)
2. Incomplete extraction: each section has only 1-2 sentences instead of full dialogue
3. Secondary: REMOVE category leakage in 22-03-23 (monastery admin/publication work being kept)

**Changes applied to `tools/extract.py`:**
1. Added GROUND RULES line: "Do not skip or summarize teaching exchanges that pass the KEEP criteria. Include the complete exchange, not just the opening statement or key sentence. The elaboration IS the teaching."
2. Expanded WORKING METHOD step 3: "Keep the remaining teaching content — including follow-up questions, elaborations, and the speaker's full explanation"
3. Expanded LONG EXCHANGES section:
   - Added: "When a topic has multiple Q&A turns (Q→A→Q→A), include all turns — do not stop after the first exchange and move on to the next topic."
   - Added: "The elaboration, follow-up questions, and further explanation in a teaching dialogue are part of the teaching, not optional context. Include them."
4. Expanded TAG GRANULARITY:
   - Added: "Each tagged section should contain the complete teaching exchange on that topic — not just an opening statement. A section with only 1-2 sentences usually indicates incomplete extraction; go back and include the full dialogue on that topic."
   - Added: "Do not extract the headline of a teaching point and skip the explanation. The explanation is the point."
5. Expanded LENGTH CHECK:
   - Added: "If you have produced more than 25 tagged sections with fewer than 150 words each on average, you are extracting headlines rather than exchanges. Return to the source and restore the full teaching dialogue under each tag."
6. Expanded REMOVE category: explicit examples for "Scheduling and rotation of Dhamma talks" and "Production work on monastery publications"

**chunk_text defaults:** unchanged (chunk_size=4000, overlap=50)

**Test command printed** for user to verify fix on 22-03-09.

**Next action:** User runs extraction test on 22-03-09, then opens a new session to evaluate whether content ratio improves toward 70%+ target and whether section count reduces to 10-20 range.

---

## Errors & Issues Encountered
- Session 2: Residual chunk overlap duplication (200-word overlap with weak detection logic caused 102.4% ratio in one file) — fixed by reducing overlap to 50 words and rewriting OVERLAP CONTEXT instruction
- Session 3: Over-aggressive OVERLAP CONTEXT (calibrated for 200-word overlap) caused unnecessary content loss in 22-03-09 (dropped 2,000 words) — fixed by recalibrating instruction to 50-word overlap size and reversing uncertainty bias
- Session 7: Fixed tag list constraint that was blocking model from creating appropriate tags for interview topics
- Session 8: Flexible tagging (Session 7) introduced headline extraction problem — model creates 38 thin sections instead of 10-20 full exchanges, causing 22-03-09 regression from 78.3% to 50.0% ratio. Fixed by adding explicit instructions to preserve complete teaching dialogues and audit for over-fragmentation in LENGTH CHECK.
- Session 9 (2026-04-28) (fast→pro→fast model): De-identification failures detected in 22-03-09 and 22-03-23

---

### Session 9 — 2026-04-28 (fast→pro→fast model) — De-identification Enforcement

**Files evaluated:**
- `Ardmk 22-03-09.md` (post-Session 8) — 9,993 words vs 10,141 source (98.5%)
- `Ardmk 22-03-23.md` (post-Session 8) — 8,491 words vs 13,364 source (63.5%)

**Assessment:**
- Session 8 fix for 22-03-09 successful: 50.0% → 98.5% — headline-extraction problem resolved ✓
- Session 8 ratio drop in 22-03-23 (86.4% → 63.5%) is NOT a regression but correct filtering of monastery logistics content (Dhamma talk scheduling, publication work) per Session 8's REMOVE additions — stays above 50% minimum ✓
- However, **critical de-identification failures detected**:
  1. Monk names leaked: "Bhante Aggacitta" appears in [meditation-tools-exploration]
  2. Monastery names leaked: "SBS", "SPS" appear throughout [investigation-practice], [upasamanussati], [sense-restraint]
  3. Country names leaked: "Sri Lanka", "Malaysia" appear in [investigation-practice], [upasamanussati], [sense-restraint], [saṅghādisesa-procedure]
  4. Layperson name leaked: "Koka" appears in [teacher-relationship]

**Root cause diagnosed:**
De-identification is applied as a content-selection filter during KEEP/REMOVE decisions, but the model reverts to near-verbatim copying once a sentence passes KEEP test. Sentences like "I came from SBS to practice..." are correctly identified as keepable teaching content, then copied verbatim without removing "SBS" identifier. The DE-IDENTIFICATION RULE positioning in the prompt comes too late.

**Changes applied to `tools/extract.py`:**
1. Modified GROUND RULES (line 11): Reinforced that de-identification applies "even when the sentence is otherwise kept verbatim for teaching content"
2. Added FINAL DE-IDENTIFICATION CHECK section at prompt's end (lines 140-148): Mandatory post-extraction scan for proper nouns (monk names, monastery names, cities, countries, layperson names) with specific replacement examples
   - Rationale: Separates de-identification from extraction decision; makes it a verification step rather than content-selection step
   - Examples show common leak patterns (sentences with [MONASTERY] or [MONK NAME] that appear as teaching content)

**chunk_text defaults:** unchanged (chunk_size=4000, overlap=50)

**Test command for user:**
```
rm output/extracted/interview/Ardmk\ 22-03-09.md
uv run python scripts/extract_dhamma.py output/corrected_pali/interview/Ardmk\ 22-03-09.md
```

Verify in the extracted output that "Bhante Aggacitta", "SBS", "SPS", "Sri Lanka", "Malaysia", and "Koka" have been replaced with generic wording ("a teacher", "a monastery", "another place", etc.).

**Next action:** User runs extraction test, then opens a new session to evaluate whether de-identification is now working correctly.

---

### Errors & Issues Encountered (Session 9 findings added above)
