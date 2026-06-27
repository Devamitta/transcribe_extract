---
name: enhance-improve
description: Cluster the active enhance backlog, design prompt/skill improvements, and archive processed notes.
trigger: /enhance-improve
---

# /enhance-improve

Full workflow doc: `kamma/enhance/enhance-improve.md`

1. `uv run python scripts/enhance_cluster.py < backlog.txt` → cluster JSON
2. `uv run python scripts/enhance_extract_state.py --section active_backlog`
3. Pro model reads clusters + filtered state only — never raw files
4. Present proposed changes for approval
5. Apply, re-evaluate, Python validation
6. Archive processed bullets + `enhance_compact.py`

**Commit-after-session rule:** Commit substantial improvements only. No-op sessions do NOT commit.
