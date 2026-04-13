# Handoff Note: 2026-04-12 - Structural JSON Fix

## Status
**SUCCESS:** The Pali correction pipeline has been fundamentally hardened. 

## Key Changes
1.  **JSON Replacement Strategy:** Replaced the "verbatim rewrite" prompt in `scripts/correct_pali.py` with a structural fix. The LLM now outputs ONLY a JSON list of corrections. Python then applies these corrections to the original text using regex word boundaries.
2.  **Zero Anomalies:** Empirical verification with `scripts/evaluate_pali.py` on the `interview` batch showed **0 anomalies** (down from 207). Infinite loops, content hallucinations, and chunk mismatches are now structurally impossible.
3.  **Archived Old Strategy:** The previous verbatim prompt engineering attempts are archived at `scripts/archive/correct_pali_verbatim_strategy.py`.
4.  **Git Integrity:** Added `scripts/archive/` to `.gitignore`.

## Critical Findings
- Zero-shot verbatim rewriting of large text chunks (2000+ words) is unreliable for complex transcripts, even with high-tier models. 
- Offloading the "editing" responsibility to Python while keeping the "identification" responsibility in the LLM is the superior architecture for this pipeline.

## Next Steps
- **Manual Review:** Inspect `output/corrected_pali/interview/` to ensure the LLM is suggesting the *correct* Pali terms from the glossary in the JSON output.
- **Review Phase:** Run `/kamma:3-review` in a fresh session with a different model (e.g., Opus) to validate the new JSON-based logic in `scripts/correct_pali.py`.
