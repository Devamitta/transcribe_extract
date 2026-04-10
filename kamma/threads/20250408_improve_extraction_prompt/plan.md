# Plan: Improve Extraction Prompt

## Overview
Replace the `SYSTEM_INSTRUCTION` in `scripts/extract_dhamma.py` to stop summarizing and instead preserve the teacher-student dialogue as a cleaned Q&A document.

## File to Modify
- `scripts/extract_dhamma.py` — `SYSTEM_INSTRUCTION` constant (lines ~14–35)

## Tasks

### [x] Task 1: Rename existing test outputs
Before making any changes, preserve current outputs for comparison:
```bash
mv output/extracted/test_3500.md output/extracted/test_3500_old.md
mv output/extracted/test_another_3500.md output/extracted/test_another_3500_old.md
```

### [x] Task 2: Replace SYSTEM_INSTRUCTION in extract_dhamma.py

Replace the current instruction (which asks for a bulleted Markdown list) with:

```python
SYSTEM_INSTRUCTION = """You are extracting Dhamma teachings from a teacher-student conversation transcript.

TASK: Clean and preserve the Dhamma dialogue. Remove ONLY: social pleasantries, logistics,
and repeated filler words ("um", "uh", false starts). Keep EVERYTHING else — questions,
answers, corrections, clarifications, analogies, examples, and the teacher's full reasoning.

OUTPUT FORMAT:
- Use Markdown section headers (## [topic-tag]) to mark the start of a new topic
  - Use standard Pāli topic tags: [khandha], [rūpa], [vedanā], [saññā], [saṅkhāra],
    [viññāṇa], [satipaṭṭhāna], [kamma], [jhāna], [paññā], [dukkha], [nibbāna], etc.
  - Multiple tags per section are fine: ## [khandha] [rūpa]
- Under each header, preserve the dialogue as a cleaned Q&A exchange:
  - **Q:** student question (condense only if the student is rambling; keep the meaning)
  - **A:** teacher's full answer — preserve their exact reasoning, examples, and
    distinctions; do NOT summarize; do NOT compress multi-sentence explanations
- When the teacher speaks multiple paragraphs, keep ALL paragraphs
- When a concept is corrected or refined mid-dialogue, keep the full correction exchange
- Multiple related questions can fall under one section header

DO NOT: summarize, paraphrase into a shorter form, or drop examples and analogies.
The goal is a cleaned transcript of the teaching, not an abstract or bullet summary."""
```

### [x] Task 3: Run ruff
```bash
uv run ruff check --fix scripts/extract_dhamma.py
uv run ruff format scripts/extract_dhamma.py
```

### [x] Task 4: Run quality extractions (full model, no --test flag)
```bash
# Do NOT use --test here — that uses a degraded model and is for smoke tests only
uv run python scripts/extract_dhamma.py test_3500.md
uv run python scripts/extract_dhamma.py test_another_3500.md
```

### [x] Task 5: Compare outputs
```bash
wc -w output/extracted/test_3500_old.md output/extracted/test_3500.md
wc -w output/extracted/test_another_3500_old.md output/extracted/test_another_3500.md
```
New output must be ≥2× old output in word count.

### [x] Task 6: Manually verify content
Check that these appear in output:
- Student questions as `**Q:**` lines
- Saliva/mouth example
- Sunburn / body affected by elements example
- Mirror / selfie example
- Bones — you cannot experience arising/ceasing of bones directly

### [~] Task 7: Present diff to user for approval
Show exact diff of the changed `SYSTEM_INSTRUCTION`. Wait for user approval before staging.

## Commit Message (prepare only — do not run git commit)
```
#extract: rewrite system_instruction to preserve q&a dialogue instead of summarizing
```
