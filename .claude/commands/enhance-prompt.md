---
name: enhance-prompt
description: Improve pipeline prompts based on evaluation harness results.
trigger: /enhance-prompt
---

# /enhance-prompt

Full workflow doc: `kamma/enhance/enhance-prompt.md`

1. `uv run python scripts/evaluate_stages.py --stage <stage>`
2. `uv run python scripts/enhance_extract_state.py --section carried_patterns --stage <stage>`
3. Pro model reads eval means + filtered state only — never raw files
4. Propose ONE change meeting qualifier gate; present for approval
5. Apply, re-evaluate, full Python validation
6. Backfill flagged production files
7. State update + `enhance_compact.py`

**Commit-after-session rule:** Commit substantial improvements only. No-op sessions do NOT commit.
