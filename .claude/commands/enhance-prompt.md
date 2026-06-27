---
name: enhance-prompt
description: Improve pipeline prompts based on evaluation harness results.
trigger: /enhance-prompt
---

# /enhance-prompt

Improve pipeline prompts by identifying low-scoring criteria in the evaluation harness and applying targeted, verified changes.

## 1. Establish Evidence
Identify the area of improvement by running the evaluation harness or using a specific dissatisfaction example.

```bash
uv run python scripts/evaluate_stages.py --stage {{stage}}
```
*Note: Provider routing follows `tools/ai_models.json`. No provider is pinned by the skill.*

## 2. Identify Change
Pick the lowest-scoring or regressed criterion from the latest `reports/eval/eval_*.md`.
- **Cross-Skill Awareness:** Before proposing a change, check `.claude/enhance-state.md` for:
  - Recent entries in **Routing Handoffs** (has `/enhance-prompt` worked on this same stage recently?)
  - Unprocessed bullets in **Active Backlog** (are there related pending issues?)
  - This prevents duplicate or conflicting edits to the same 5 files if another skill is also editing them.
- Read carried patterns from `.claude/enhance-state.md`'s **Carried Patterns** section, filtered by `[stage: extract|polish|pali]` tags (e.g., "Headline extraction risk").
- Propose ONE targeted change to address the issue.
- **Qualifier gate (hard precondition — do not propose an edit unless this is met):** a defect earns a prompt edit only if it EITHER appears in a production `reports/batch/…` report OR reproduces in ≥3 of 4 direct-generation trials (judge bypassed). A single golden-set finding or a single judge pass is explicitly insufficient — the ledger has re-learned this lesson at least 3 times (Sessions 11, 13, 15) from non-deterministic judge/model behavior that looked like a real defect but wasn't. If a finding doesn't meet either bar, do not propose a change; log it for further direct-repro testing or drop it as noise.

### Allowed Files Only
Changes are restricted to these 5 files:
1. `tools/pali.py`
2. `tools/extract.py`
3. `tools/polish.py`
4. `tools/data/pali_overrides.json`
5. `tools/data/pali_examples.json`

## 3. Background Review (Optional)
Launch a background Gemini process to provide a second opinion on the proposed prompt diff.
```bash
agy --model "Gemini 3.5 Flash (Low)" --print-timeout 120s --print "Review this prompt improvement diff... {{diff}}"
```

## 4. Human Approval Gate
Present the proposed change to the user for approval.
- Display: `Before` → `After`.
- Explain the rationale and how it addresses the evaluation findings.
- Use `approve/skip/defer`.

## 5. Apply & Verify
If approved, apply the change and re-verify performance.

1. **Re-evaluate:** Run the harness again to see the impact.
   ```bash
   uv run python scripts/evaluate_stages.py --stage {{stage}} --test
   ```
   *Compare before/after means.*

2. **Python Validation Gate:** If any `.py` file was modified, run the full validation suite:
   ```bash
   uv run ruff check --fix {{file}}
   uv run ruff format {{file}}
   uv run python -m pyright {{file}}
   uv run --with pyrefly pyrefly check --min-severity warn {{file}}
   # Run targeted tests if applicable
   # uv run pytest tests/test_{{feature}}.py -v
   ```

## 6. Backfill Flagged Production Files
Once the harness confirms the fix, reprocess production files already flagged for the criterion just fixed — a confirmed-bad prompt's output never gets left as-is in `output/`.

1. **Find affected files:** search `reports/batch/batch_{{stage}}_*.md` for files flagged on the criterion just fixed (e.g. size ratio < 0.60, or the specific low-scoring criterion).
2. **Delete their stale output**, then reprocess one file at a time — the runner skips any file whose output already exists, so deletion is required before a re-run picks it up:
   ```bash
   rm "output/extracted/{{folder}}/{{flagged_file}}"
   uv run python scripts/extract_dhamma.py "output/corrected_pali/{{folder}}/{{flagged_file}}"
   ```
   (swap `extract_dhamma.py`/`extracted` for `polish_extract.py`/`polished` when `{{stage}}` is `polish`)
3. **Confirm the fix landed:**
   ```bash
   uv run python scripts/evaluate_batch.py --stage {{stage}} --folder {{folder}}
   ```
4. If a file is still flagged after the fix, stop — don't loop indefinitely. Defer it and surface to the user as a possible legitimately-short talk rather than a prompt defect.

## 7. State Update
Update `.claude/enhance-state.md` with:
- The session summary under **Session Ledger** → **### /enhance-prompt** (include: last_run timestamp, stage, criterion improved, whether any existing Carried Pattern was marked resolved).
- Any new patterns or risks under **Carried Patterns** (with appropriate stage tags).
- If this session fixed (and backfill in Step 6 confirmed) an existing Carried Pattern marked `(open, YYYY-MM-DD)`, change its marker to `(resolved, YYYY-MM-DD)` — this is what un-blocks `/enhance`'s batch processing for that stage. If the fix is still unverified or backfill found residual flagged files, leave it `(open, ...)`.
- Run `uv run python scripts/enhance_compact.py` (deterministic, idempotent, no LLM — enforces retention rules).

## 8. Session Handoff
`.claude/enhance-state.md` now reflects this session's outcome — patterns updated, Session Ledger written, backfill results recorded. Tell the user it's safe to start a **new session** before the next step — further `/enhance-prompt` work, or `/enhance` to resume batch processing.

**Commit-after-session rule:** If this session produced a substantial improvement (a resolved pattern, a judge fix, a backfill, a cleared semantic batch, an applied prompt change), prepare and make a descriptive commit before handoff. Trivial/no-op sessions (gate-blocked, investigation-only, state-ledger-writes-only) do NOT commit. End commit messages with the standard `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` line.
