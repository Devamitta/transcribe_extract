# Quality Control

Five ongoing feedback loops, each targeting a different stage of the pipeline:

| Loop | Stage | Thread |
|------|-------|--------|
| Transcription Quality | Raw Whisper output | `ongoing_transcription_feedback` |
| Pali Correction | LLM Pali correction | `ongoing_pali_correction_feedback` |
| Semantic Evaluation | Corrected transcripts | `ongoing_semantic_evaluation_loop` |
| Extract Quality | Dhamma extraction | `ongoing_extract_quality` |
| Polish Quality | Post-extraction polish | `ongoing_polish_quality` |

All loop state, logs, and handoffs live in `kamma/threads/ongoing_loops/`.

---

## 1. Transcription Quality Loop

Iterative feedback loop to identify and filter Whisper hallucinations (phrase loops, silence artifacts, anomalies) at the raw transcript level.

**Scope:** `scripts/transcribe.py`, `output/transcribed/`
**Thread:** `kamma/threads/ongoing_loops/ongoing_transcription_feedback/`

### Steps

```bash
# 1. Extract anomalies from a transcription batch
uv run python scripts/extract_errors.py --input-dir output/transcribed/sangha/

# 2. Compare with a previous report after filter changes
uv run python scripts/diff_reports.py log/old_report.md log/new_report.md

# 3. Extract audio snippets to verify real hallucination vs. natural stutter
uv run python scripts/extract_snippets.py log/report_20260411.md
```

Based on findings, update hallucination filters in `scripts/transcribe.py` (punctuation-agnostic checks, tiered repetition detection). A pro model is required for error analysis — stop and switch before that phase.

---

## 2. Pali Correction Feedback Loop

Continuous loop for refining the Pali correction prompt. Catches structural errors with automated tools and semantic meaning-flip hallucinations (e.g., `winner` → `Vinaya`) via manual grep.

**Scope:** `tools/pali.py` (`PALI_SYSTEM_INSTRUCTION`), `scripts/evaluate_pali.py`, `tools/glossary.py`
**Thread:** `kamma/threads/ongoing_loops/ongoing_pali_correction_feedback/`

**Critical limitation:** `evaluate_pali.py` cannot detect semantic flips. Always run a manual grep sweep:

```bash
grep -riE "vagina|winner|linear|epidemic" output/corrected_pali/
```

### Steps

1. Run `evaluate_pali.py` and perform grep sweep
2. **Stop — switch to pro model** for analysis
3. **Stop — wait for user approval** of improvement proposal
4. Apply approved refinements to `tools/pali.py`
5. Re-run `scripts/correct_pali.py` and verify with both tools

Note: The prompt is significantly hardened. Monitor for regression rather than expanding scope.

---

## 3. Semantic Evaluation Loop

Detects remaining Whisper hallucinations and contextually wrong passages after Pali correction — catches English-word substitutions and garbled Pali terms that the correction step missed.

**Scope:** `output/corrected_pali/` (corrections applied here only — never `output/transcribed/`)
**Thread:** `kamma/threads/ongoing_loops/ongoing_semantic_evaluation_loop/`

### Prerequisite

Before starting a session, run batch semantic evaluation:

```bash
uv run python scripts/batch.py --stage semantic --folder interview --limit 10
```

### Direct Mode (Real-Time)

```bash
uv run python scripts/evaluate_semantic.py interview
# Test mode (first 2 chunks only)
uv run python scripts/evaluate_semantic.py -t interview
# Specific file
uv run python scripts/evaluate_semantic.py output/corrected_pali/interview/Talk.md
```

Reports written to `reports/semantic/<subfolder>/<filename>.md`.

### Session Flow

1. Read only fresh semantic reports (newer than last reviewed mtime in `handoff.md`)
2. Pro model classifies findings, plans fixes, gets user approval
3. Fast model applies approved fixes via `temp/apply_semantic_fixes.py`
4. Re-evaluate to confirm clean
5. Log session in `handoff.md`; delete `temp/apply_semantic_fixes.py`

Deferred Dhamma-Vinaya terms requiring manual review are logged in `manual_corrections.md`.

---

## 4. Extract Quality Loop

Recurring loop for reviewing and improving the Dhamma extraction pipeline. Compares source transcripts against extracted outputs, proposes prompt changes, and applies them after user approval.

**Scope:** `tools/extract.py` (`EXTRACT_SYSTEM_INSTRUCTION`, chunk settings only)
**Thread:** `kamma/threads/ongoing_loops/ongoing_extract_quality/`

**Extraction goal:** Public-release output — extract Dhamma-Vinaya teaching content, de-identify personal stories, remove monk/monastery names while preserving teaching value.

### Loop Structure

1. **Phase 1 (fast model):** Read source and extracted files, collect evidence, prepare findings
2. **Stop — switch to pro model**
3. **Phase 2 (pro model):** Analyze findings, diagnose root cause, propose prompt diff
4. **Stop — wait for user approval**
5. **Phase 3 (fast model):** Apply approved changes, lint, print test command, log session

This thread never runs extraction scripts — it prints the command and the user runs it.

---

## 5. Polish Quality Loop

Recurring loop for reviewing and improving the Dhamma polish pipeline. Compares extracted vs polished outputs, proposes prompt changes, and applies them after user approval.

**Scope:** `tools/polish.py` (`POLISH_SYSTEM_INSTRUCTION`, validation settings only)
**Thread:** `kamma/threads/ongoing_loops/ongoing_polish_quality/`

### Loop Structure

1. **Phase 1 (fast model):** Read extracted and polished files, collect evidence, prepare findings
2. **Stop — switch to pro model**
3. **Phase 2 (pro model):** Analyze findings, diagnose root cause, propose prompt diff
4. **Stop — wait for user approval**
5. **Phase 3 (fast model):** Apply approved changes, lint, print test command, log session

Common failure modes: over-compression, content loss, word count constraint violations.
This thread never runs polish scripts — it prints the command and the user runs it.
