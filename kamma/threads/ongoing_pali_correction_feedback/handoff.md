# Handoff: Ongoing Pali Correction Feedback Loop

## Migration Note (2026-04-29)
The batch loop (`20260427_ongoing_batch_pali_feedback/`) has been closed. History from that loop has been migrated to `archive/handoff_archive.md`. Active work continues in this thread using direct script execution (`scripts/correct_pali.py`).

---

## Current Active State (2026-04-29)

### Architecture
- **Prompt Location:** `tools/pali.py` → `get_pali_system_instruction(file_path)`
- **Direct Script:** `scripts/correct_pali.py` (Gemini, real-time)
- **Batch Script:** `scripts/batch.py` (OpenAI, async) — deprecated for this loop
- **Evaluation:** `scripts/evaluate_pali.py` — **note: misses semantic meaning-flip errors**

### Folder-Aware Glossary
- `scripts/correct_pali.py` uses folder-aware prompt: includes `MONASTICS` glossary only for 'sangha' folder files.
- Interview files exclude monastic glossary to prevent over-correction of common Pali words (e.g., `pāmojja` → `Pamodadhammika`).

---

## Key Lessons From Batch Loop (Must Not Forget)

### Critical Findings
1. **evaluate_pali.py is insufficient:** Automated script only catches character/word count changes. It **cannot** detect semantic "meaning flip" hallucinations (e.g., `vagina` → `paññā`, `winner` → `Vinaya`). **Manual grep sweeps are mandatory.**

2. **Silent failures in manual patches:** If `temp/apply_fixes.py` dictionary is incomplete, patches report "0 anomalies" while data remains corrupted. Always verify with grep against the full Rule 10 list.

3. **Structural corruption:** LLM can merge paragraphs or delete "noise" text, causing chunk count mismatches. Rule 13 (SURGICAL INTEGRITY) addresses this.

4. **Diminishing returns:** The prompt has been hardened significantly. Further improvements will yield marginal returns. Monitor for regression, not expansion.

### High-Impact Semantic Overrides (Rule 10)
These patterns are **ALWAYS** hallucinations and must be corrected regardless of perceived English plausibility:
- `vagina/vaginas` → `paññā` or `sampajañña`
- `winner`, `linear` → `Vinaya`
- `the singer/singers` → `the Sangha`
- `Europa` → `arūpa`
- `cookie/cookies/cook` → `kutī/kutis`
- `epidemic` → `Abhidhamma`
- `red cock noise` → `recognition`
- `Russian canon` → `Theravada canon`
- `five-year-old` → `five aggregates`
- `wire tomorrow` → `vaya-dhamma`
- `much money car` → `Majjhima Nikāya`
- And 40+ more patterns documented in `tools/pali.py` Rule 10.

---

## Operating Rules (Post-Batch)

1. **Handoff-first:** Read this file before every session.
2. **Manual grep sweep:** Run grep against the full Rule 10 override list before concluding any session.
3. **Stop/review gates:** Switch model for analysis, get user approval before implementing changes.
4. **Economy mandate:** Never re-run expensive LLM work for trivial fixes. Manually patch current data instead.
5. **Diminishing returns:** If remaining anomalies are minor or unfixable without breaking other things, recommend concluding the loop.
6. **Archive rule:** Keep only the 2 most recent sessions in handoff.md; older history goes to archive/handoff_archive.md.

---

## Verification Command
After any correction run:
```bash
grep -riE "vagina|winner|linear|epidemic" output/corrected_pali/
```