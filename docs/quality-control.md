# Quality Control

Quality control is orchestrated via slash-command skills. These skills replace the former ongoing Kamma loops:

| Skill | Purpose | State Location |
|-------|---------|----------------|
| `/semantic-fix` | Corrected transcript data fixes | `.claude/semantic-fix-state.md` |
| `/prompt-quality` | Pali, extract, and polish prompt/data tuning | `.claude/prompt-quality-state.md` |

The original thread folders are archived under `kamma/archive/ongoing_loops/`.

---

## Quality Skills

### `/semantic-fix` (Semantic Evaluation)

Semantic evaluation detects remaining Whisper hallucinations and contextually wrong passages after Pali correction. This skill fixes data in `output/corrected_pali/`; it does not tune prompts.

**Trigger:** `/semantic-fix`

**Procedure:**
1. **Run Detection:** The skill runs `scripts/evaluate_semantic.py` to generate reports under `reports/semantic/`. Provider routing follows `tools/ai_models.json`.
2. **Queue Selection:** Selects up to 10 unreviewed reports by mtime vs `.claude/semantic-ledger.json`.
3. **Classification:** Findings are classified as True Positive (Fix), True Positive (Defer), or False Positive.
4. **Approval Gate:** Human approval is required before applying fixes.
5. **Apply:** Fixes are applied to transcripts via a generated `temp/apply_semantic_fixes.py` script.
6. **Verification:** Re-evaluates modified files and updates state/ledger.

Deferred Dhamma-Vinaya terms requiring manual review are logged in `.claude/semantic-manual-corrections.md`.

### `/prompt-quality` (Prompt Quality)

Improves the Pali, extract, and polish stage prompts using the golden-set harness results.

**Trigger:** `/prompt-quality`

**Procedure:**
1. **Establish Evidence:** Run `scripts/evaluate_stages.py` (Antigravity-only) to identify low-scoring criteria.
2. **Identify Change:** Pick ONE targeted change for `tools/pali.py`, `tools/extract.py`, `tools/polish.py`, `tools/data/pali_overrides.json`, or `tools/data/pali_examples.json`.
3. **Approval Gate:** Human approval is required before applying prompt changes.
4. **Verification:** Re-runs the harness and records before/after means.
5. **Validation:** Runs the full Python validation suite (ruff, pyright, pyrefly, pytest) on any changed code.

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

---

## Transcription Checks

There is no LLM-judge transcription eval because there are no ground-truth
transcripts. Use deterministic tools for raw transcript quality:

```bash
uv run python scripts/extract_errors.py --input-dir output/transcribed/sangha/
uv run python scripts/diff_reports.py log/old_report.md log/new_report.md
uv run python scripts/extract_snippets.py log/report_20260411.md
```
