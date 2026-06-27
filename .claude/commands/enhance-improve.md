---
name: enhance-improve
description: Cluster the active enhance backlog, design prompt/skill improvements, and archive processed notes.
trigger: /enhance-improve
---

# /enhance-improve

Analyze the enhance improvements backlog, group similar issues, propose and apply targeted prompt or logic changes, and archive the processed backlog notes.

> [!NOTE]
> This command is best executed using a Strong model (Opus / Sonnet) since it involves complex logic analysis and code generation.

---

## 1. Read Backlog
Read the **Active Backlog** section from `.claude/enhance-state.md`.
If the section is empty, report that there is no pending work and stop.

---

## 2. Cluster + Analyze
1. **Cross-Skill Awareness:** Before proposing changes, check `.claude/enhance-state.md`:
   - Recent **Routing Handoffs** — has `/enhance-prompt` worked on these same 5 files recently?
   - Any unresolved entries in **Carried Patterns** that are still marked `(open, ...)`?
   - This prevents duplicate edits if `/enhance-prompt` is actively working on the same stage.
2. **Clustering (delegation opportunity):** Cluster the backlog bullets into logical groups (e.g. over-compression, formatting issues, Pali terminology errors). This administrative grouping is a good candidate for delegation to a fast/simple sub-agent if the backlog is large — hand it the unprocessed bullets and ask it to cluster them by theme, returning a labeled list. **Use the Agent tool with `model: "haiku"` explicitly** (mechanical grouping does not need a strong model; omitting the override defaults to the strong model and is far more expensive). You then analyze and propose targeted changes for each cluster.
3. For each cluster, propose a targeted, minimal change to the prompt or configuration data.
4. **Allowed Files Only:** Your edits must be restricted to these 5 files:
   - `tools/pali.py`
   - `tools/extract.py`
   - `tools/polish.py`
   - `tools/data/pali_overrides.json`
   - `tools/data/pali_examples.json`

---

## 3. Human Approval Gate
Present the proposed changes clearly to the user:
- Show a `Before` → `After` diff for each file.
- Explain the rationale for the change and how it addresses specific clustered backlog items.
- Ask for explicit user approval before writing any changes.
- Use `approve/skip/defer` for the proposed edits.

---

## 4. Apply + Verify
Once approved, execute the changes:
1. **Apply Changes:** Use your code edit tools to write the approved changes to the selected files.
2. **Re-evaluate:** Run the evaluation harness on the affected stage to verify there are no regressions:
   ```bash
   uv run python scripts/evaluate_stages.py --stage extract --test
   ```
3. **Python Validation Gate:** For all modified `.py` files, run the mandatory verification suite:
   ```bash
   uv run ruff check --fix <file>
   uv run ruff format <file>
   uv run python -m pyright <file>
   uv run --with pyrefly pyrefly check --min-severity warn <file>
   ```

---

## 5. Archive & Truncate
1. Append the processed backlog bullets to `.claude/enhance-improvements-history.md` under a dated heading:
   ```markdown
   ## YYYY-MM-DD
   - [bullet 1]
   - [bullet 2]
   ```
2. **Archiving:** Remove the processed bullets from `.claude/enhance-state.md`'s **Active Backlog** section, replacing them with nothing (the section gets emptied). The durable record now lives in the history file.
3. **Maintenance Check:** Run `uv run python scripts/enhance_compact.py` (deterministic, idempotent, no LLM — enforces retention rules on history).

---

## 6. Session Handoff
The backlog is archived in `.claude/enhance-improvements-history.md` and emptied from `.claude/enhance-state.md`'s **Active Backlog**. Tell the user it's safe to start a **new session** before resuming `/enhance`.

**Commit-after-session rule:** If this session produced a substantial improvement (a resolved pattern, a judge fix, a backfill, a cleared semantic batch, an applied prompt change), prepare and make a descriptive commit before handoff. Trivial/no-op sessions (gate-blocked, investigation-only, state-ledger-writes-only) do NOT commit. End commit messages with the standard `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` line.
