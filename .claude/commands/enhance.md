---
name: enhance
description: Orchestrate execution, enhance control, and improvement prompting for the interview pipeline.
trigger: /enhance
---

# /enhance

Orchestrate the interview library pipeline by detecting state, processing files in small batches, running batch enhance evaluation, and managing the enhance backlog.

> [!IMPORTANT]
> **Context Discipline Rule:**
> To keep the session context light and fast (target ≤120k tokens), the agent must **NEVER** read raw transcripts or full extraction/polishing outputs into its context. Read only:
> 1. State ledger and file counts.
> 2. Flagged-only reports (`reports/batch/...`).
> 3. Specific short flagged excerpts needing human review.

---

## 1. Detect State
Run the following read-only commands to detect the current interview pipeline state. Do NOT read any transcript files.

```bash
# Count inputs and outputs
echo "Corrected Pāli files:" && ls output/corrected_pali/interview/ | wc -l
echo "Extracted files:"      && ls output/extracted/interview/*.md 2>/dev/null | wc -l
echo "Polished files:"       && ls output/polished/interview/*.md 2>/dev/null | wc -l
echo "Latest batch reports:" && ls -t reports/batch/ 2>/dev/null | head -5
```

Report the counts to the user in plain terms.

**Unreviewed semantic backlog check (first-class priority, mandatory):** Compute the unreviewed count = (number of report files on disk in `reports/semantic/interview/`) − (number of entries in `.claude/semantic-ledger.json`'s `processed_files`). Report this exact number to the user. If the count is **greater than 0**, recommend the user run `/enhance-semantic-fix` BEFORE any Action A/B/C batch work below — the semantic backlog takes priority over fresh batch processing.

**Open systemic issue check (mandatory):** Read `.claude/enhance-state.md`'s Carried Patterns for any entry marked `(open, YYYY-MM-DD)`.
- Entries tagged `[stage: extract|polish|pali]` mean that stage's generation prompt is known-broken — do NOT run Action A/B/C batch processing for that stage; it would only produce more flagged output. Report the open pattern to the user and route directly to `/enhance-prompt` instead. Once `/enhance-prompt` resolves it, the pattern is marked resolved/removed there and this check clears on the next `/enhance` run.
- Entries tagged `[engineering, …]` (judge/harness reliability defects, e.g. bugs in `tools/eval_judge.py`) are NOT generation-prompt defects and must NOT block Action A/B/C batch processing for any stage. Report the open engineering pattern to the user and note that a dedicated engineering session (with `tools/eval_judge.py` in scope) is needed to resolve it — do not route this to `/enhance-prompt`, whose allowed-files scope cannot fix it.

**Diagnostic-vs-Gate Distinction:** When a user excludes "agent evaluation" from their request, don't drop diagnostic-only scripts like `evaluate_batch.py` — it can be run purely to read ratio/score numbers without routing to `/enhance-prompt` or `/enhance-semantic-fix` (judge-as-diagnostic, distinct from judge-as-gate). If the user says "no evaluation", clarify: are they skipping batch QC entirely, or skipping *only* the approval/routing gate (keeping diagnostic runs for numbers)?

---

## 2. Choose + Run Next Action
Based on state detection, decide the next action. By default, process a small batch of size `SESSION_BATCH = 5` (overridable by the user). Skip this step entirely if the open-systemic-issue check above fired for the relevant stage.

### Action A: Extracted < Corrected Pāli
If the number of extracted files is less than corrected Pāli files, process the next batch:
1. **Extract Dhamma:**
   ```bash
   uv run python scripts/extract_dhamma.py --folder interview --limit 5
   ```
2. **Polish Extract:**
   ```bash
   uv run python scripts/polish_extract.py --folder interview --limit 5
   ```
3. **Run Batch QC (Extraction):**
   ```bash
   uv run python scripts/evaluate_batch.py --stage extract --folder interview --limit 5
   ```
4. **Run Batch QC (Polishing):**
   ```bash
   uv run python scripts/evaluate_batch.py --stage polish --folder interview --limit 5
   ```

### Action B: Polished < Extracted
If extraction is ahead but polishing is behind:
1. **Polish Extract:**
   ```bash
   uv run python scripts/polish_extract.py --folder interview --limit 5
   ```
2. **Run Batch QC (Polishing):**
   ```bash
   uv run python scripts/evaluate_batch.py --stage polish --folder interview --limit 5
   ```

### Action C: All processed, Run QC Only
If all files are processed but some need QC rerun:
```bash
uv run python scripts/evaluate_batch.py --stage polish --folder interview --limit 5
```

**Background Execution Guidance:** The batch scripts (`extract_dhamma.py`, `polish_extract.py`, `evaluate_batch.py`) can be time-consuming (8-48s per file serially). For Actions A/B/C, recommend running them in the background so you can continue to the next session/step without waiting:
```bash
# Run in background and get notified when done
caffeinate -i nice -n 10 uv run python scripts/extract_dhamma.py --folder interview --limit 5 &
# or use nohup for a completely detached process
nohup uv run python scripts/evaluate_batch.py --stage extract --folder interview --limit 5 > /tmp/batch_qc.log 2>&1 &
```

---

## 3. Surface Flagged Items
Locate the generated batch report: `reports/batch/batch_<stage>_<folder>_<ts>.md`.
1. Read **ONLY** the batch report. Clean files only appear as a summary count.
2. For each flagged file in the report, if needed to understand the reason, read **ONLY** the specific passage/excerpt from the source and candidate file (use targeted line ranges or small reads).
3. Present each flagged file to the user with:
   - Filename
   - Size ratio (target guideline 75%, floor 60%)
   - Failed criteria and score (e.g. Completeness: 3/5)
   - Judge's reason
4. Present an **Approve / Skip / Defer** gate for each flagged item to let the user decide whether to accept the output anyway, skip it, or defer it for correction.

**Delegation Opportunity:** Reading many flagged items' passages is mechanical work (line-range lookups, summarizing found passages). If the batch is large, you may delegate this read-only lookup work to a fast/simple sub-agent — hand it the batch report and source folder path, ask it to fetch the specific line ranges for each flagged item and return the passages. **Use the Agent tool with `model: "haiku"` explicitly** (line-range lookups do not need a strong model; omitting the override defaults to the strong model and is far more expensive). You then present the findings to the user. This keeps the main session focused on judgment calls while delegating retrieval work, respecting the Context Discipline Rule (no raw transcripts in the main context, only focused excerpts).

---

## 4. Batch Verdict + Routing
Give a summary verdict of the batch:
- **Systemic enhance issues** (e.g. consistent over-compression, wrong tag format, LLM criteria failures): before recommending anything, write the finding to `.claude/enhance-state.md` under **Carried Patterns** — batch report path, affected criterion, root-cause hypothesis, and flagged-file count. `/enhance-prompt`'s own evidence step (golden-set harness) does NOT see production batch reports, so this handoff must be written down now; a future session cannot recover it from conversation history. Only then recommend the user run `/enhance-prompt`.
- **Upstream transcription/Pāli data issues** (e.g. spelling errors, hallucinations in source): recommend the user run `/enhance-semantic-fix`. Write a **Routing Handoff** entry to `.claude/enhance-state.md` under **Routing Handoffs** — date, "→ /enhance-semantic-fix", one-line finding, pointer to the batch report and flagged files.
- **Clean batch / Minor issues resolved:** recommend "Run `/enhance` again for the next batch."

---

## 5. State + Backlog Management
1. **Session Ledger:** Record this session's work by writing a new dated entry to `.claude/enhance-state.md` under the **Session Ledger** → **### /enhance** section. Include: last_run timestamp, files processed, batch report paths, outcomes of the Step 3 approve/skip/defer gate, and routing decisions from Step 4.
2. **Update Carried Patterns:** For any systemic issue routed to `/enhance-prompt`, the entry is already written in Step 4 (Carried Patterns section).
3. **Append Backlog:** For any enhance, prompt, or extraction issues spotted during the run that cannot be fixed on the spot, append a one-line bullet describing the issue to `.claude/enhance-state.md` under **Active Backlog**. **Do not duplicate an issue already routed via the Step 1 open-pattern check or written to Carried Patterns in Step 4** — a systemic issue gets exactly one home (the Carried Pattern), not two competing write-ups in two backlogs that `/enhance-prompt` and `/enhance-improve` could independently act on.
4. **Maintenance Check:** After writing to the hub, run `uv run python scripts/enhance_compact.py` (deterministic, idempotent, no LLM — enforces all hub/archive/history retention rules).
5. **Backlog Warning:** Count the unprocessed bullets in `.claude/enhance-state.md`'s **Active Backlog** section. If there are **5 or more** unprocessed bullets, warn the user:
   > [!WARNING]
   > The enhance improvement backlog has 5 or more issues. Please run `/enhance-improve` (preferably using a Pro model) to cluster, analyze, and address these issues.

---

## 6. Session Handoff
All required state for this run is now on disk in `.claude/enhance-state.md` (Session Ledger, Carried Patterns, Active Backlog, and Routing Handoffs). Tell the user it is safe, and recommended, to start a **new session** before invoking the next skill (`/enhance-prompt`, `/enhance-semantic-fix`, `/enhance-improve`, or `/enhance` again). A fresh session carries no accumulated context overhead; the persisted state is sufficient to resume without it.

**Commit-after-session rule:** If this session produced a substantial improvement (a resolved pattern, a judge fix, a backfill, a cleared semantic batch, an applied prompt change), prepare and make a descriptive commit before handoff. Trivial/no-op sessions (gate-blocked, investigation-only, state-ledger-writes-only) do NOT commit. End commit messages with the standard `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` line.
