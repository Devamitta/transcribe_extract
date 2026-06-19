# Quality Control

Quality control now has two active recurring loops:

| Loop | Stage | Thread |
|------|-------|--------|
| Semantic Evaluation | Corrected transcript data fixes | `kamma/threads/ongoing_loops/ongoing_semantic_evaluation_loop/` |
| Prompt Quality | Pali, extract, and polish prompt/data tuning | `kamma/threads/ongoing_loops/ongoing_prompt_quality/` |

The old manual loops for transcription, Pali correction, extract, and polish were
archived under `kamma/archive/ongoing_loops/`. Prompt quality is now evaluated
with the golden-set harness below.

---

## Stage Quality Eval Harness

`scripts/evaluate_stages.py` runs fixed golden excerpts through the current LLM
stage prompts and asks an Antigravity Pro judge to score the output.

```bash
PROVIDER=agy uv run python scripts/evaluate_stages.py
PROVIDER=agy uv run python scripts/evaluate_stages.py --stage extract
PROVIDER=agy uv run python scripts/evaluate_stages.py --stage polish --limit 3
PROVIDER=agy uv run python scripts/evaluate_stages.py --stage pali --test
```

Flags:

- `--stage pali|extract|polish`: evaluate one stage; default is all stages.
- `--limit N`: evaluate the first N golden excerpts per selected stage.
- `--test`: evaluate the first 2 excerpts per selected stage. Provider test
  models apply as usual.

The harness is intentionally Antigravity-only. Startup exits `1` unless
`PROVIDER` is `agy` or `antigravity-cli`, then probes the judge model
`Gemini 3.1 Pro (Low)`.

### Golden Set

Golden excerpts live in `eval/golden/{pali,extract,polish}/` with provenance in
`eval/golden/manifest.md`. The whole `eval/` tree is gitignored because excerpts
may contain raw, un-de-identified transcript text.

Rules:

- Keep excerpts frozen once curated. Do not edit existing excerpt text because
  history comparisons depend on stable input.
- Add new numbered excerpts instead of changing old ones.
- Record source path, approximate location, and reason in the manifest.
- Keep each excerpt near production chunk size, roughly 3,000-5,000 characters.

### Scoring

For every excerpt the harness makes two LLM calls:

1. Generate candidate output using the normal provider path
   (`tools.provider.generate_with_timeout`) and the same prompt assembly used by
   the pipeline.
2. Judge with `tools.antigravity_cli.generate_content`, model
   `Gemini 3.1 Pro (Low)`, temperature `0.0`, strict JSON response.

Rubrics:

- `pali`: Pali restoration correctness; no meaning-flips or over-correction;
  non-Pali text preserved.
- `extract`: completeness; fidelity; de-identification; `## [tag]` and Q/A
  structure.
- `polish`: content fidelity; readability improvement; structure preservation.

Deterministic checks also run:

- Extract output must be at least 50% of source word count.
- Polish output must stay within `POLISH_WORD_TOLERANCE` (`+/-15%`) of input word
  count.

### Reports And History

Each run writes:

- `reports/eval/eval_<YYYYMMDD_HHMMSS>.md`: per-excerpt scores, judge reasons,
  deterministic check results, and stage means.
- `reports/eval/history.json`: append-only per-stage history with timestamp,
  prompt hash, generation model list, judge model, criterion means, and overall
  mean.

Prompt hashes include the assembled stage system instruction. For Pali they also
include raw bytes from `tools/data/pali_overrides.json` and
`tools/data/pali_examples.json`.

Exit codes:

- `0`: clean run.
- `1`: hard failure, such as provider failure, judge parse failure, or failed
  deterministic check.
- `2`: regression on a full-stage run. A stage overall mean dropped by at least
  `0.5` compared with the previous full-stage history entry for the same stage.

Runs using `--test` or `--limit` are marked as sampled in `history.json`. They
still write scorecards and history entries, but they do not trigger regression
exit code `2`; one- or two-excerpt smokes are too noisy to use as baselines.

Run this harness after any approved change to `tools/pali.py`, `tools/extract.py`,
`tools/polish.py`, `tools/data/pali_overrides.json`, or
`tools/data/pali_examples.json`.

### Prompt Quality Loop

Use `kamma/threads/ongoing_loops/ongoing_prompt_quality/` for prompt or Pali-data
tuning sessions. The workflow is:

1. Run or read the latest `reports/eval/` scorecard for the affected stage.
2. Diagnose the smallest prompt/data change from concrete evidence.
3. Get explicit user approval before editing.
4. Apply the approved change.
5. Rerun `scripts/evaluate_stages.py --stage <stage>` and compare means.

Known carried-forward risks:

- Extract "headline extraction": dense topic-shifting input can become many thin
  sections instead of complete teaching exchanges.
- Pali meaning flips: review `vagina|winner|linear|epidemic` carefully when
  changing Pali correction behavior.

---

## Semantic Evaluation Loop

Semantic evaluation detects remaining Whisper hallucinations and contextually
wrong passages after Pali correction. This loop fixes data in
`output/corrected_pali/`; it does not tune prompts.

**Thread:** `kamma/threads/ongoing_loops/ongoing_semantic_evaluation_loop/`

### Prerequisite

Before starting a session, run batch semantic evaluation:

```bash
uv run python scripts/batch.py --stage semantic --folder interview --limit 10
```

### Direct Mode

```bash
uv run python scripts/evaluate_semantic.py interview
uv run python scripts/evaluate_semantic.py -t interview
uv run python scripts/evaluate_semantic.py output/corrected_pali/interview/Talk.md
```

Reports are written to `reports/semantic/<subfolder>/<filename>.md`.

### Session Flow

1. Read only fresh semantic reports newer than the last reviewed mtime in
   `handoff.md`.
2. Classify findings, plan fixes, and get user approval.
3. Apply approved fixes to `output/corrected_pali/`.
4. Re-evaluate to confirm clean.
5. Log the session in `handoff.md`.

Deferred Dhamma-Vinaya terms requiring manual review are logged in
`manual_corrections.md`.

---

## Transcription Checks

There is no LLM-judge transcription eval because there are no ground-truth
transcripts. Use deterministic tools for raw transcript quality:

```bash
uv run python scripts/extract_errors.py --input-dir output/transcribed/sangha/
uv run python scripts/diff_reports.py log/old_report.md log/new_report.md
uv run python scripts/extract_snippets.py log/report_20260411.md
```
