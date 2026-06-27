---
name: enhance-semantic-fix
description: Run semantic evaluation queue, classify findings, and apply Pali/Dhamma corrections.
trigger: /enhance-semantic-fix
---

# /enhance-semantic-fix

Orchestrate the semantic evaluation loop: run detection, classify findings (fix/defer/false-positive), and apply corrections to transcripts.

## 1. Detection
Run the detection script to evaluate transcripts and generate/update reports. The script skips reports that are already current.

```bash
uv run python scripts/evaluate_semantic.py interview {{args}}
```
*Note: Provider routing follows `tools/ai_models.json`. No provider is pinned by the skill.*

## 2. Queue Selection
Identify unreviewed reports in `reports/semantic/` by comparing mtime against `.claude/semantic-ledger.json`.
- Normalize filenames with NFC before comparison.
- Limit to **SESSION_LIMIT = 10** reports per session.
- Log excess reports as pending.

## 3. Classification

### Context Check + Classification (mandatory delegation, per file)
The report quotes each passage with surrounding context (a `**Context:**` line, added by the detection script — see `scripts/evaluate_semantic.py`). Never classify from the bare passage alone; use the context line first. Only fall back to grepping the actual source file in `output/corrected_pali/<folder>/` for the rare finding where the report's context line is itself insufficient — most findings should not need this fallback. The isolated snippet routinely makes wrong suggestions look plausible and right readings look wrong (e.g. a real Pali term misread as a name once quoted out of context).

**Mandatory delegation (cost control):** Classification (and the occasional grep fallback) is token-heavy and must run on the fast model, not the coordinator — this is not optional.

**First, read the hub once yourself** and copy out only the `[stage: semantic]` Carried Pattern lines from `.claude/enhance-state.md` (≈6 lines, <1k tokens). That small blob is the only hub content a subagent needs.

**Chunk, don't fan out per file.** Group the selected reports into **2–3 subagent calls** (roughly equal report counts each), NOT one subagent per report. Quality is identical — same rule, same files — and classification works mostly from each finding's `Context:` line, so a chunked subagent stays light.

For each subagent — **`model: "haiku"` explicitly** — hand it: the findings for its chunk (which already include context), the source file paths for those reports (for the rare fallback grep), the `[stage: semantic]` Carried Pattern blob **inlined directly** (not as a path), and a pointer to `.claude/enhance-semantic-reference.md` (a 36-line file) as the one file it may open for the DO-NOT-FLAG list. **Never give a subagent the path to the full `.claude/enhance-state.md`** — it is ~8k tokens of mostly-irrelevant hub (other skills' ledgers, routing handoffs), and N subagents each reading it is the single biggest cost leak this skill had. A <1k-token blob inlined into 2–3 prompts is far cheaper than the full hub read N times. Give each subagent this strict rule:

> Only tag a finding **TP-fix** if the correction is a single word or proper name with direct, verifiable phonetic correspondence to the source audio garble (e.g. "Bhatimokha"→"Pāṭimokkha"). Multi-word phrase or compound-term reconstructions that rely on semantic/contextual guessing rather than phonetic match must be tagged **TP-defer**, never TP-fix — regardless of how plausible the meaning looks.

Bake this rule into the subagent prompt from the start, every time. Never run a batch without it and then manually re-filter the coordinator's own judgment over the output afterward — if a batch needs re-filtering, fix the subagent prompt and re-run it, don't re-judge the output by hand on the strong model.

**Required return format (compact only):** the subagent returns one line per finding — `finding | classification | one-line reason` — and nothing else. No raw transcript excerpts, no per-finding reasoning chains, no restated context. This is what keeps the coordinator's context light regardless of file size or finding count; a verbose subagent return defeats the purpose of delegating.

Classify each finding as:
- **TP-fix:** True positive, confident fix given full context, passes the strict rule above.
- **TP-defer:** True positive, but needs manual review (append to `.claude/semantic-manual-corrections.md`).
- **FP:** False positive, no change needed.

### Heuristics & Known Patterns
Refer to `.claude/enhance-state.md`'s **Carried Patterns** section (tagged `[stage: semantic]`) for:
- Carried patterns (e.g., "Teams" → "Temples", "Dog" → "Dhamma", "China" → "Chanda/Citta").
- Meaning-Flip Grep List: `vagina|winner|linear|epidemic`.
- Open to `.claude/enhance-semantic-reference.md` (sidecar) for:
  - Known Error Patterns (large reference list from past sessions).
  - DO NOT FLAG rules (e.g., historical suicide refs, vivid analogies).

### Background Review (Optional)
You may launch a background Gemini process to provide a second opinion on the classifications.
```bash
agy --model "Gemini 3.5 Flash (Low)" --print-timeout 120s --print "Review these semantic evaluation findings... {{findings}}"
```

## 4. Human Approval Gate
Do not present every finding — the user cannot evaluate a long list and it wastes their attention on things that are already settled. Apply confident **TP-fix** items directly (they were already confirmed against real context in step 3). Bring to the user's attention **only** the doubtful/suspicious items:
- **TP-defer** items, and
- any case where the evaluator's suggestion looked plausible from the snippet but full context changed the call (flips to FP, or to a different fix than suggested).

For each item raised, show: the surrounding context (not just the snippet) → the issue → your reasoning → recommended action (skip/defer/alternate fix). State your classification plainly; ask the user to weigh in only on these flagged items, not the whole batch.

**Deferred Items Warning:** Before appending **TP-defer** items to `.claude/semantic-manual-corrections.md`, check if it currently has 5 or more unresolved items. If so, warn the user:
> [!WARNING]
> `.claude/semantic-manual-corrections.md` has 5+ deferred items. These are permanently-deferred Pali/Dhamma guesses with no mechanism prompting a fresh look. Consider flagging this file for a future `/enhance-semantic-fix` review pass once more transcripts/context could confirm a pattern.

## 5. Apply Fixes
Generate and execute a temporary script to apply approved fixes to the files in `output/corrected_pali/`.

```bash
# Example generation
cat <<EOF > temp/apply_semantic_fixes.py
import sys
from pathlib import Path

def apply_fix(file_path, old, new):
    content = Path(file_path).read_text()
    Path(file_path).write_text(content.replace(old, new))

if __name__ == "__main__":
    apply_fix("output/corrected_pali/example.md", "old text", "new text")
EOF

uv run python temp/apply_semantic_fixes.py
```

## 6. Verification & State Update
1. **Re-evaluate:** Run `evaluate_semantic.py` on the modified files to confirm they are now clean.
2. **Manual Corrections:** Append **TP-defer** items to `.claude/semantic-manual-corrections.md`.
3. **Pali Rules:** If new persistent patterns emerged, propose an update to `tools/pali.py::get_semantic_eval_instruction()`.
4. **Update State:**
   - Update `.claude/enhance-state.md` with:
     - New entries or updates to **Carried Patterns** (tagged `[stage: semantic]`).
     - Session summary under **Session Ledger** → **### /enhance-semantic-fix** (last_run timestamp, reports processed, fixes applied, deferred items count).
   - Run `uv run python scripts/enhance_compact.py` (deterministic, idempotent, no LLM — enforces retention rules).
   - Update `.claude/semantic-ledger.json` with new mtime markers.
   - Clean up `temp/apply_semantic_fixes.py`.

## 7. Session Handoff
`.claude/enhance-state.md` and `.claude/semantic-ledger.json` are updated. Tell the user it's safe to start a **new session** before resuming `/enhance` or running `/enhance-semantic-fix` again for the next batch.

**Commit-after-session rule:** If this session produced a substantial improvement (a resolved pattern, a judge fix, a backfill, a cleared semantic batch, an applied prompt change), prepare and make a descriptive commit before handoff. Trivial/no-op sessions (gate-blocked, investigation-only, state-ledger-writes-only) do NOT commit. End commit messages with the standard `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` line.
