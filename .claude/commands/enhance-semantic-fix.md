---
name: enhance-semantic-fix
description: Run semantic evaluation queue, classify findings, and apply Pali/Dhamma corrections.
trigger: /enhance-semantic-fix
---

# /enhance-semantic-fix

Full workflow doc: `kamma/enhance/enhance-semantic-fix.md`

1. `uv run python scripts/evaluate_semantic.py interview`
2. `uv run python scripts/enhance_queue.py --folder interview` → read queue
3. `uv run python scripts/classify_semantic.py <reports>` → read `temp/semantic_classifications.md`
4. Auto-apply TP-fix; present TP-defer and borderline items for approval
5. `uv run python scripts/enhance_apply_fixes.py fixes.json`
6. Re-evaluate, update state, run `enhance_compact.py`

**Commit-after-session rule:** Commit substantial improvements only. No-op sessions do NOT commit.
