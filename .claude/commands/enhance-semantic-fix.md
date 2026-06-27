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

### Context Check (mandatory, before classifying)
The report only quotes a short snippet — never classify from that snippet alone. For every finding, grep the surrounding sentence(s) from the actual source file in `output/corrected_pali/<folder>/` first. The isolated snippet routinely makes wrong suggestions look plausible and right readings look wrong (e.g. a real Pali term misread as a name once quoted out of context). Only classify after reading the real context.

**Delegation Opportunity (B10):** The context-grep step is pure retrieval (grep for pattern, return lines with context). If doing this manually for many findings would be repetitive, you may delegate it to a fast/simple sub-agent (via the Agent tool) — hand it the list of findings and the folder path, ask it to grep each finding and return the surrounding context. The sub-agent runs with the Context Discipline Rule (no raw transcripts in the main agent's context — only the focused grep output returns to you for classification). This keeps the main agent's context light while delegating mechanical retrieval work.

Analyze findings in the selected reports. Classify each as:
- **TP-fix:** True positive, confident fix given full context.
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

**Deferred Items Warning (B3):** Before appending **TP-defer** items to `.claude/semantic-manual-corrections.md`, check if it currently has 5 or more unresolved items. If so, warn the user:
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
     - Run `wc -l .claude/enhance-state.md` and apply compaction if it exceeds 200 lines.
   - Update `.claude/semantic-ledger.json` with new mtime markers.
   - Clean up `temp/apply_semantic_fixes.py`.

## 7. Session Handoff
`.claude/enhance-state.md` and `.claude/semantic-ledger.json` are updated. Tell the user it's safe to start a **new session** before resuming `/enhance` or running `/enhance-semantic-fix` again for the next batch.

**Commit-after-session rule:** If this session produced a substantial improvement (a resolved pattern, a judge fix, a backfill, a cleared semantic batch, an applied prompt change), prepare and make a descriptive commit before handoff. Trivial/no-op sessions (gate-blocked, investigation-only, state-ledger-writes-only) do NOT commit. End commit messages with the standard `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` line.
