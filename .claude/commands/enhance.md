---
name: enhance
description: Orchestrate execution, enhance control, and improvement prompting for the interview pipeline.
trigger: /enhance
---

# /enhance

Full workflow doc: `kamma/enhance/enhance.md`

1. `uv run python scripts/enhance_detect.py --json` → read state
2. If `unreviewed_semantic > 0` → route to `/enhance-semantic-fix` first
3. If open patterns block a stage → route to `/enhance-prompt`
4. Otherwise: run Action A/B/C batch processing, surface flagged items, present approve/skip/defer gate
5. Write session ledger, run `enhance_compact.py`
6. Handoff: safe for new session

**Commit-after-session rule:** Commit substantial improvements only. No-op sessions do NOT commit.
