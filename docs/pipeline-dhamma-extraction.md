# Dhamma Extraction Pipeline

This pipeline turns raw transcripts into a polished, tag-grouped Dhamma database:

1. Transcribe audio
2. Correct Pāli and Buddhist terminology
3. Extract public-safe Dhamma teaching sections
4. Polish extracted prose
5. Write a privacy scan report
6. Consolidate tagged sections into `master_dhamma_database.md`

## Wrapper

```bash
./extract_run.sh
```

Start from a later stage when earlier outputs already exist:

```bash
./extract_run.sh --from transcribe
./extract_run.sh --from pali
./extract_run.sh --from extract
./extract_run.sh --from polish
./extract_run.sh --from consolidate
```

`--from consolidate` runs the privacy report first, then consolidation. The wrapper does not run a separate provider probe before LLM stages; each LLM stage uses its first real request as the availability check and exits non-zero if required output cannot be produced after retries. Logs are written to `log/extract_run_<timestamp>.log`.

For manual provider/auth troubleshooting, run:

```bash
uv run python scripts/check_keys.py --text
```

Stage script exit codes are:

- `0`: all queued files completed
- `1`: hard failure; wrapper aborts
- `2`: partial file failures; wrapper warns and continues

Failed chunked files keep their `.<filename>.tmp` resume files. Re-run the wrapper later to retry failed chunks without re-paying for completed chunks.

## Pāli Correction

```bash
uv run python scripts/correct_pali.py [file]
uv run python scripts/correct_pali.py --folder sangha
uv run python scripts/correct_pali.py --limit 5
```

Input: `output/transcribed/`

Output: `output/corrected_pali/`

The script mirrors relative paths, skips files whose output already exists, and uses the shared chunk runner retry policy: 3 attempts per chunk, then 2 retry rounds for still-failed chunks. Deterministic corpus overrides such as `winner -> Vinaya` are applied locally before the LLM call. Applied local and LLM corrections are logged per file under `reports/pali_corrections/`.

## Dhamma Extraction

```bash
uv run python scripts/extract_dhamma.py [file]
uv run python scripts/extract_dhamma.py --folder interview
uv run python scripts/extract_dhamma.py --limit 5
```

Input: `output/corrected_pali/`

Output: `output/extracted/`

The extraction prompt removes identifying details and emits sections headed with `## [topic-tag]`. `NO_POINTS` chunks are excluded. Outputs below 50% of input word count are reported as warnings but are still written.

## Polishing

```bash
uv run python scripts/polish_extract.py [file]
uv run python scripts/polish_extract.py --folder interview
uv run python scripts/polish_extract.py --limit 5
uv run python scripts/polish_extract.py --dry-run
```

Input: `output/extracted/`

Output: `output/polished/`

`--dry-run` lists the files that would be processed and does not call the provider or write output. There is no `--output-dir` flag; output always mirrors into `output/polished/`.

Polish validates each chunk against `POLISH_WORD_TOLERANCE` before finalizing. A validation failure is retried like a provider failure; if it still fails, the temp file is kept and no final polished file is written.

## Privacy Report

```bash
uv run python scripts/check_privacy.py
uv run python scripts/check_privacy.py --fix
uv run python scripts/check_privacy.py --polished-dir output/polished --extracted-dir output/extracted --report-dir reports/privacy
```

The scanner reads `output/polished/` first and falls back to `output/extracted/` for files that have not been polished. Reports are written to `reports/privacy/privacy_<timestamp>.md`.

The scan is report-only by default and exits `0` even when hits are found. `--fix` rewrites flagged polished files in place with generic replacements such as `a teacher` and `a monastery`, and records every replacement in the report. Fallback extracted files are never rewritten by `--fix`.

## Consolidation

```bash
uv run python scripts/consolidate.py
uv run python scripts/consolidate.py --polished-dir output/polished --extracted-dir output/extracted --output master_dhamma_database.md
```

Consolidation prefers `output/polished/<relative-path>` and falls back to `output/extracted/<relative-path>`. It recursively scans nested folders, parses `## [topic-tag]` headers, and writes `master_dhamma_database.md` grouped by tag with source attribution for every section. Untagged content is grouped under `## Untagged Sources`.
