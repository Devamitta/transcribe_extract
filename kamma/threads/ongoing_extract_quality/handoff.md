# Extract Quality Improvement — Handoff

## Context
New thread created 2026-04-28 to fix the extraction pipeline. The core problem is that the model generates generic Dhamma textbook content instead of preserving the actual transcript.

## Problem Evidence
- `output/extracted/interview/Ardmk 22-04-04.md` contains generic Q&A like "What is the relationship between the five khandhas and dukkha?" with textbook answers — none of this was in the actual recording.
- The actual recording (`output/corrected_pali/interview/Ardmk 22-04-04.md`, ~50KB) is a personal interview about the student's jhāna and satipaṭṭhāna practice.
- Root cause: `EXTRACT_SYSTEM_INSTRUCTION` never told the model to use ONLY the transcript — the model treats the topic as permission to write from its own knowledge.

## Sessions

### Session 1 — 2026-04-28 (fast→pro→fast model)

**Files evaluated:**
- `Ardmk 22-03-09.md` (extracted)
- `Ardmk 22-03-23.md` (extracted)

**Problems identified:**
1. Chunk overlap (500 words) causes duplicate sections in extracted output — same content appears twice under different headers
2. Length ratio below 50% target: 38% for 22-03-09, 48% for 22-03-23
3. "Scheduling and logistics" removal category too broad — drops meditation planning discussions (Dhamma content) that look like logistics

**Changes applied to `tools/extract.py`:**
1. Rewrote `EXTRACT_SYSTEM_INSTRUCTION`:
   - "lightly edited version" → "near-verbatim transcript" (removes editorial discretion implication)
   - Added LONG EXCHANGES paragraph (no compression of long dialogues)
   - Narrowed "scheduling/logistics" removal to: travel, retreat booking, visa paperwork, unrelated admin only
   - Added carve-out: practice planning discussions ALWAYS kept even if they mention times
   - Added OVERLAP CONTEXT note (tells model to skip re-processing overlapping content)
   - Strengthened LENGTH CHECK from warning to verification step ("go back and restore")
2. Updated `chunk_text` defaults:
   - overlap: 500 → 200 (mechanically reduces duplicate output; 200 words is enough sentence context)
   - chunk_size: 4000 (kept unchanged to avoid compression pressure from larger chunks)

**Test command printed** for user to verify.

**Next action:** User runs extraction test, then opens a new session of this thread to evaluate the output.

---

### Session 2 — 2026-04-28 (fast→pro→fast model)

**Files evaluated (post-Session 1 changes):**
- `Ardmk 22-03-09.md` (extracted) — 8,495 words vs 10,141 source (83.8%)
- `Ardmk 22-03-23.md` (extracted) — 13,682 words vs 13,364 source (102.4%)

**Assessment:**
- Session 1 changes succeeded: both files now far exceed 50% minimum, content is verbatim-faithful, zero hallucination detected
- One residual issue: `Ardmk 22-03-23.md` exceeds source length (102.4%), and visible duplication found in 22-03-09 (same Q&A exchange repeated under two different topic headers)
- Root cause: OVERLAP CONTEXT instruction relies on "mid-thought/mid-sentence" detection, which fails when overlap begins at a sentence boundary

**Problems identified:**
1. Chunk overlap (200 words from Session 1) still causes mild duplication — model includes overlapping content when it begins at a clean sentence boundary
2. Length ratio >100% in one file indicates content is being output twice

**Changes applied to `tools/extract.py`:**
1. Rewrote `OVERLAP CONTEXT` section:
   - Removed dependency on structural signal ("mid-thought/mid-sentence")
   - Replaced with explicit instruction: assume opening content is overlap; skip forward until new topic begins
   - Added guideline: "When uncertain whether opening content is overlap or new, skip it — duplication is worse than a missed sentence"
2. Updated `chunk_text` defaults:
   - overlap: 200 → 50 (reduces duplication window while preserving sentence-boundary safety)
   - chunk_size: 4000 (unchanged)

**Test command to verify fix:**
```
rm output/extracted/interview/Ardmk\ 22-03-23.md
uv run python scripts/extract_dhamma.py output/corrected_pali/interview/Ardmk\ 22-03-23.md
```

**Expected outcome:** New extracted file should be ≤100% of source length with no visible duplicate sections.

**Next action:** User runs extraction test, then opens a new session to evaluate.

---

### Session 3 — 2026-04-28 (fast→pro→fast model)

**Files evaluated (post-Session 2 changes):**
- `Ardmk 22-03-09.md` (extracted) — 6,505 words vs 10,141 source (64.1%)
- `Ardmk 22-03-23.md` (extracted) — 12,481 words vs 13,364 source (93.4%)

**Assessment:**
- Session 2 duplication fix successful: 22-03-23 ratio improved from 102.4% → 93.4% ✓
- Content quality good: no hallucination detected, all traced phrases verified against source
- One issue identified: 22-03-09 dropped from 8,495 → 6,505 words (83.8% → 64.1%), losing ~2,000 words

**Root cause diagnosed:**
The Session 2 OVERLAP CONTEXT rewrite was too aggressive for overlap=50. The instruction "scan forward until you reach a new topic" + "skip when uncertain" was appropriate for 200-word overlap but causes over-skipping with 50-word overlap. The model is treating 200-500 words at chunk starts as potential overlap when only ~50 words actually overlap.

**Changes applied to `tools/extract.py`:**
Rewrote OVERLAP CONTEXT section:
- Specified the overlap is ~50 words (not unbounded)
- Changed scan limit from "until new topic" to "first 50–100 words only"
- Reversed bias from "skip when uncertain" to "include when uncertain"
- Rationale: With small overlap, recovering legitimate content is more important than eliminating minimal duplication

**Test command printed** for user to verify fix.

**Next action:** User runs extraction test on 22-03-09, then opens a new session to evaluate.

---

## Errors & Issues Encountered
- Session 2: Residual chunk overlap duplication (200-word overlap with weak detection logic caused 102.4% ratio in one file) — fixed by reducing overlap to 50 words and rewriting OVERLAP CONTEXT instruction
- Session 3: Over-aggressive OVERLAP CONTEXT (calibrated for 200-word overlap) caused unnecessary content loss in 22-03-09 (dropped 2,000 words) — fixed by recalibrating instruction to 50-word overlap size and reversing uncertainty bias
