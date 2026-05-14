# OpenAI Batch Pipeline

Run Pāli correction, Dhamma extraction, and semantic evaluation using the OpenAI Batch API at **50% lower cost** than real-time calls. Batches typically complete within **minutes to hours**.

## When to use this

Use the batch pipeline when you have many files to process and cost matters more than speed. For 1–2 urgent files, use the real-time scripts (`correct_pali.py`, `extract_dhamma.py`) instead. Batches are ideal for processing 10+ files in one go.

---

## Setup

Add to `.env`:
```
OPENAI_API_KEY=sk-...
OPENAI_PALI_MODEL=gpt-4o-mini      # optional, defaults to gpt-4o-mini
OPENAI_EXTRACT_MODEL=gpt-4o-mini   # optional, defaults to gpt-4o-mini
OPENAI_SEMANTIC_MODEL=gpt-4o-mini  # optional, defaults to gpt-4o-mini
```

---

## Usage

**Full pipeline** — prepare, submit, auto-poll (every 30s), and retrieve:

```bash
# Both pali + extract (default)
uv run python scripts/batch.py

# Pali correction only
uv run python scripts/batch.py --stage pali

# Extract only
uv run python scripts/batch.py --stage extract

# Semantic evaluation only
uv run python scripts/batch.py --stage semantic

# Limit to first N files (useful for testing)
uv run python scripts/batch.py --stage pali --limit 1

# Specific subfolder
uv run python scripts/batch.py --stage pali --folder interview

# Custom poll interval (default 30 seconds)
uv run python scripts/batch.py --stage extract --poll-interval 40

# Submit only, don't wait for completion
uv run python scripts/batch.py --stage semantic --no-wait
```

**Check status:**

```bash
# Check latest batch for a task
uv run python scripts/batch.py --status pali

# List all tracked jobs
uv run python scripts/batch.py --list
```

---

## How it works

1. **Prepare** — Scans input directory, skips already-processed files, writes JSONL to `output/batch_input/`.
2. **Submit** — Uploads JSONL, creates OpenAI batch job, saves job ID to `output/batch_jobs.json`.
3. **Poll** — Checks status every N seconds, prints real-time progress.
4. **Retrieve** — When complete, downloads results and writes output files.

Progress output:
```
Stage: pali
[QUEUE] talk1.md
1 already done, 1 to process
Submitting 14 requests...
Creating batch...
Polling every 30s
Ctrl+C to stop and retrieve manually later
[07:27:54] validating — 0/0
[07:28:25] in_progress — 2/14
[07:29:25] completed — 14/14
Downloading results...
  Written: output/corrected_pali/interview/talk1.md
1 files written
```

**If interrupted (Ctrl+C):** Batch keeps running. Resume with `--status` to check, or wait and run again — the script will skip already-processed files.

---

## Output format

**Pali-corrected files** (`output/corrected_pali/`): JSON arrays of corrections applied to the text.

**Extracted Dhamma points** (`output/extracted/`): Structured Q&A format with Pāli topic tags:
```markdown
## [khandha] [dukkha]
**Q:** What is the relationship between the five khandhas and dukkha?  
**A:** The five khandhas—rūpa, vedanā, saññā, saṅkhāra, and viññāṇa—are the components of personal experience...
```

---

## Notes

- **Skip logic:** Files are skipped if output exists, whether from real-time or batch. Safe to re-run.
- **Job tracking:** All batches are recorded in `output/batch_jobs.json` with status and timestamps.
- **Batch window:** OpenAI has a 24h completion window, but batches usually finish within minutes to hours.
