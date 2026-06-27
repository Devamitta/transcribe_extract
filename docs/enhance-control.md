# Enhance Control

Enhance control in the interview pipeline is driven by a unified front door `/enhance` command, which orchestrates batch execution, automated LLM-judged evaluation, and improvement routing.

## The Enhance Control Ecosystem

The enhance control workflow is powered by the following components:

| Command / Script | Purpose | Type | State / Output Location |
|------------------|---------|------|------------------------|
| `/enhance` | **Single Front Door:** Detects state, runs batches, triggers QC, surfaces flags. | Orchestrator Skill | Shared hub `.claude/enhance-state.md` |
| `/enhance-semantic-fix` | Reviews and applies corrections to Whisper transcription hallucinations. | Engine Skill | Shared hub `.claude/enhance-state.md` (+ sidecar `enhance-semantic-reference.md`, `.claude/semantic-ledger.json`, `.claude/semantic-manual-corrections.md`) |
| `/enhance-prompt` | Targets regressions and improves stage prompts using the golden excerpt harness. | Engine Skill | Shared hub `.claude/enhance-state.md` |
| `/enhance-improve` | Clusters enhance backlog notes and applies prompt/skill improvements. | Engine Skill | Shared hub `.claude/enhance-state.md` (Active Backlog) → `.claude/enhance-improvements-history.md` |
| `scripts/evaluate_batch.py` | Production QC engine assessing file pairs for completeness and size ratios. | Python Script | `reports/batch/` |

> **State architecture (2026-06-18):** all four `/enhance*` skills now share one
> orchestration hub, `.claude/enhance-state.md`, with owned sections (Carried
> Patterns, Routing Handoffs, Active Backlog, Session Ledger) and a Maintenance
> size-cap/compaction convention. Bulky semantic reference data lives in the sidecar
> `.claude/enhance-semantic-reference.md`; older sessions in
> `.claude/enhance-session-archive.md`. Each skill reads only the section(s) it needs.

---

## Workflow Principles

### 1. Gradual Loop Usage ("Process-QC-Improve")
Rather than running large batches blindly, the pipeline is designed for incremental scalability:
1. **Process a Few:** Run `/enhance` to run a small batch (default: 5 files) through the extraction and polishing stages.
2. **Enhance Control:** `/enhance` runs `scripts/evaluate_batch.py` to compare source and candidate texts, checking for over-compression (flag floor 60%, target 75%) and completeness.
3. **Surface Flags:** Any failed files are presented at a human approval gate.
4. **Improve:** If systemic errors appear, issues are added to the backlog and addressed via `/enhance-improve`.
5. **Reprocess & Scale:** Once prompts/rules are tuned, re-run evaluation and scale up to the next batch.

### 2. Context-Light Design
To maintain Sonnet/Opus session efficiency and avoid token bloat (target ≤120k tokens/session):
- The orchestrator `/enhance` **never** reads full transcriptions or raw outputs.
- All heavy text extraction, parsing, and LLM judging occur within Python subprocesses.
- The agent only reads summary counts, the flagged-only report (`reports/batch/...`), and specific short excerpts for flagged files.

### 3. Backlog, Warning, and History Mechanism
- When `/enhance` detects a enhance defect that cannot be solved with a trivial local fix, it appends a one-line description to the **Active Backlog** section of `.claude/enhance-state.md`.
- If the Active Backlog accumulates **5 or more** unprocessed issues, the agent warns the user to run `/enhance-improve` to address them.
- `/enhance-improve` groups active backlog items, proposes a cohesive redesign, and upon approval, applies it and archives the processed issues to `.claude/enhance-improvements-history.md` under a dated heading (emptying the hub's Active Backlog).

### 4. Open Pattern Gate (with Engineering Carve-out)
- `/enhance` checks `.claude/enhance-state.md`'s Carried Patterns for entries marked `(open, YYYY-MM-DD)` before running any Action A/B/C batch.
- Entries tagged `[stage: extract|polish|pali]` mean that stage's generation prompt is known-broken — they block Action A/B/C batch processing for that stage and route to `/enhance-prompt`.
- Entries tagged `[engineering, …]` (judge/harness reliability defects, e.g. bugs in `tools/eval_judge.py`) are **not** generation-prompt defects and do **not** block batch processing for any stage — judge bugs cannot be fixed within `/enhance-prompt`'s allowed-files scope, so they route to a dedicated engineering session instead.

### 5. Semantic Backlog Priority
- `/enhance` computes the unreviewed semantic count (reports on disk in `reports/semantic/interview/` minus entries in `.claude/semantic-ledger.json`) on every run and reports it.
- When the count is greater than 0, `/enhance` recommends running `/enhance-semantic-fix` before any Action A/B/C batch work — the semantic backlog takes priority over fresh batch processing.

---

## Enhance Skills

### `/enhance-semantic-fix` (Semantic Evaluation)
Semantic evaluation detects remaining Whisper hallucinations and contextually wrong passages after Pāli correction. This skill fixes data in `output/corrected_pali/`; it does not tune prompts.

**Trigger:** `/enhance-semantic-fix`

**Procedure:**
1. **Run Detection:** The skill runs `scripts/evaluate_semantic.py` to generate reports under `reports/semantic/`. Provider routing follows `tools/ai_models.json`.
2. **Queue Selection:** Selects up to 10 unreviewed reports by mtime vs `.claude/semantic-ledger.json`.
3. **Classification:** Findings are classified as True Positive (Fix), True Positive (Defer), or False Positive.
4. **Approval Gate:** Human approval is required before applying fixes.
5. **Apply:** Fixes are applied to transcripts via a generated `temp/apply_semantic_fixes.py` script.
6. **Verification:** Re-evaluates modified files and updates state/ledger.

Deferred Dhamma-Vinaya terms requiring manual review are logged in `.claude/semantic-manual-corrections.md`.

### `/enhance-prompt` (Prompt Enhance)
Improves the Pāli, extract, and polish stage prompts using the golden-set harness results.

**Trigger:** `/enhance-prompt`

**Procedure:**
1. **Establish Evidence:** Run `scripts/evaluate_stages.py` (Antigravity-only) to identify low-scoring criteria.
2. **Identify Change:** Pick ONE targeted change for `tools/pali.py`, `tools/extract.py`, `tools/polish.py`, `tools/data/pali_overrides.json`, or `tools/data/pali_examples.json`.
3. **Approval Gate:** Human approval is required before applying prompt changes.
4. **Verification:** Re-runs the harness and records before/after means.
5. **Validation:** Runs the full Python validation suite (ruff, pyright, pyrefly, pytest) on any changed code.

---

## Stage Enhance Eval Harness

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
transcripts. Use deterministic tools for raw transcript enhance:

```bash
uv run python scripts/extract_errors.py --input-dir output/transcribed/sangha/
uv run python scripts/diff_reports.py log/old_report.md log/new_report.md
uv run python scripts/extract_snippets.py log/report_20260411.md
```
