# Specification: Improve Extraction Prompt to Reduce Summarization

## Problem

`scripts/extract_dhamma.py` outputs a bulleted Markdown list that collapses rich teacher-student dialogue into 2–4 sentence summaries. Despite the "DO NOT SUMMARIZE" instruction, the bullet-list format structurally forces compression. Key examples, multi-paragraph explanations, student questions, and dialogue flow are lost.

**Input:** ~5000-word raw dialogue (e.g., `output/transcribed/test_3500.md`)
**Current output:** ~24 bullets / ~5KB — a ~73% reduction in content
**Desired output:** Cleaned Q&A dialogue preserving teacher's full explanations — target ≥2× current word count

## What It Should Do

### output/extracted/
Files should look like cleaned dialogue — not an abstract or summary:

```markdown
## [khandha] [rūpa]

**Q:** What is rūpa in the context of the five aggregates?

**A:** I would not say the four elements are the experience of hardness and softness. That is a manifestation — how you can experience or witness them. But even without you witnessing them, the four elements are still there. Rūpa is materiality — the material building blocks...

**Q:** But does it relate to personal experience?

**A:** The rūpa is the same whether you cling to it or not. Upādāna comes in when the mind takes the body personally...
```

### Rules for the new prompt
- Topic tags as Markdown section headers (`## [tag1] [tag2]`)
- `**Q:**` for student questions (concise if rambling, but kept)
- `**A:**` for teacher answers — near-verbatim, full paragraphs, NO compression
- When teacher speaks multiple paragraphs → keep all
- When teacher corrects or refines mid-dialogue → keep the correction
- Remove ONLY: social pleasantries, logistics, repeated filler ("um", "uh", false starts)

## Constraints
- Only change: `SYSTEM_INSTRUCTION` constant in `scripts/extract_dhamma.py`
- No changes to chunk logic, provider, or file I/O
- Must pass `ruff check --fix` and `ruff format`

## Test Commands

> **Note:** Do NOT use `--test` flag for quality evaluation. `--test` uses a lighter/cheaper
> model and is for smoke-testing only (does the pipeline run?). Quality evaluation requires
> the full production model.

```bash
# Rename old outputs first (to preserve for comparison)
mv output/extracted/test_3500.md output/extracted/test_3500_old.md
mv output/extracted/test_another_3500.md output/extracted/test_another_3500_old.md

# Run full model on test files (quality evaluation)
uv run python scripts/extract_dhamma.py output/corrected_pali/test_3500.md
uv run python scripts/extract_dhamma.py output/corrected_pali/test_another_3500.md

# Compare word counts
wc -w output/extracted/test_3500_old.md output/extracted/test_3500.md
wc -w output/extracted/test_another_3500_old.md output/extracted/test_another_3500.md
```

## How We'll Know It's Done
- [ ] New output word count ≥2× old output word count
- [ ] Student questions appear as `**Q:**` lines
- [ ] Key examples preserved: saliva/mouth, sunburn/body, mirror/selfie, bones
- [ ] Teacher's multi-paragraph answers are intact (not collapsed)
- [ ] `ruff check --fix` and `ruff format` pass on `scripts/extract_dhamma.py`
- [ ] User has manually reviewed and approved output quality
