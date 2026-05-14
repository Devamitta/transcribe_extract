# Quality Control

Two overlapping loops that catch different classes of transcription errors:

1. **Transcription Quality Loop** — filters Whisper hallucinations (phrase loops, anomalies) at the raw transcript level.
2. **Semantic Evaluation** — detects contextually wrong passages and English-word substitutions that survive Pāli correction.

---

## 1. Transcription Quality Loop

Iterative feedback loop to identify and filter "fuzzies" (Whisper hallucinations, phrase loops, anomalies).

Detailed logs and progress of this loop are tracked in: `kamma/threads/ongoing_transcription_feedback/`

### Step 1: Extract Anomalies (Fuzzies)

```bash
uv run python scripts/extract_errors.py --input-dir output/transcribed/sangha/
```

Generates a report in `reports/` detailing repeated phrases and suspicious sequences with surrounding context.

### Step 2: Compare with Baselines

If you have changed filters in `scripts/transcribe.py`, compare with a previous report to verify improvements:

```bash
uv run python scripts/diff_reports.py log/old_report.md log/new_report.md
```

### Step 3: Manual Verification

Extract specific audio snippets to verify whether an anomaly is a real hallucination or natural stutter:

```bash
uv run python scripts/extract_snippets.py log/report_20260411.md
```

Saves short audio clips for each anomaly in the report.

### Step 4: Refine Filters

Based on the reports, update the hallucination filters in `scripts/transcribe.py`. We use punctuation-agnostic checks and tiered repetition detection to distinguish between natural speech stutters and Whisper glitches.

### Step 5: Verify

Rerun the transcription on the problematic files to ensure the "fuzzies" are now correctly skipped or handled.

---

## 2. Semantic Evaluation

Detects remaining Whisper hallucinations and contextually wrong passages after Pāli correction — catches English-word substitutions and garbled terms the Pāli correction step missed.

### Direct Mode (Real-Time)

```bash
uv run python scripts/evaluate_semantic.py interview
```

Writes per-file reports in `reports/semantic/<subfolder>/<filename>.md`.

**Options:**
- Specify a folder: `uv run python scripts/evaluate_semantic.py interview` (processes `output/corrected_pali/interview/`)
- Test mode (first 2 chunks only): `uv run python scripts/evaluate_semantic.py -t interview`
- Specific file: `uv run python scripts/evaluate_semantic.py output/corrected_pali/interview/Talk.md`

### Batch Mode

```bash
# Semantic evaluation only
uv run python scripts/batch.py --stage semantic --folder interview

# With limit (useful for testing)
uv run python scripts/batch.py --stage semantic --folder interview --limit 1

# Submit only, retrieve later
uv run python scripts/batch.py --stage semantic --no-wait
```

Output: Per-file markdown reports in `reports/semantic/<subfolder>/<filename>.md` listing all findings.

### Review & Apply Corrections

1. Run the evaluator (above)
2. Review each finding interactively (true positive vs. false positive)
3. Apply approved corrections back to `output/corrected_pali/`
4. Re-run evaluator to verify the fixes worked

For details, see: `kamma/threads/ongoing_semantic_evaluation_loop/plan.md`
