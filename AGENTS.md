# Project Rules

Apply these in addition to your baseline global instructions `~/.claude/CLAUDE.md`.

## Project Overview

Dhamma Transcriber & Extractor - A local pipeline that converts MP3 Dhamma talks into Markdown transcripts using MLX Whisper, then extracts core Dhamma points using Gemini API.

## Python Type Hints
- Please add type hints to all code, especially when it is missing in existing code.
- Use modern type hints not old type hints
  - Use `dict[str, str]` not `Dict[str, str]`
  - Use `tuple[str, str]` not `Tuple[str, str]`
  - Use `list[str]` not `List[str]`
  - Use `| None` not Optional[None]

## Use Path from Pathlib
- Use Path for anything related to filepaths, not os.

## Project Structure
- `audio/english`, `audio/russian`, `audio/sangha`, `audio/interview` — raw MP3 inputs by pipeline branch
- `video/english`, `video/russian` — raw video inputs for YouTube upload pipelines
- `output/transcribed` — Whisper transcripts (Markdown)
- `output/corrected_pali` — LLM Pali-corrected transcripts
- `output/extracted` — Dhamma point extractions (Markdown + metadata)
- `output/polished` — polished/post-processed extractions
- `output/batch_input` — OpenAI batch API job inputs
- `output/english_audio`, `output/english_thumbnails`, `output/english_youtube` — English upload assets
- `output/russian_audio`, `output/russian_thumbnails`, `output/russian_youtube` — Russian upload assets
- `reports/semantic` — semantic evaluation reports
- `reviews/` — pipeline review outputs
- `temp/` — scratch space (gitignored)

## Pipeline Commands
All scripts live in `scripts/`. Use the shell wrappers at the project root:

- **Full Dhamma pipeline** (transcribe → Pali correct → extract → consolidate): `./run_pipeline.sh`
- **Batch transcription only** (sangha + interview + dhamma): `./transcribe.sh`; single context: `./transcribe.sh --context sangha|interview|dhamma`
- **YouTube pipeline** (English or Russian): `./yt_run.sh --lang ru|en [folder] [--video-mode]` (defaults: `russian`/`english`)

Individual scripts (run from project root):
- Transcription: `caffeinate -i nice -n 10 uv run python scripts/transcribe.py`
- Extraction: `uv run python scripts/extract_dhamma.py`
- Pali correction: `uv run python scripts/correct_pali.py`
- Consolidation: `uv run python scripts/consolidate.py`

## Code Quality
- Align CLI flags and validation constants (e.g., word-count tolerance) early in the spec phase to avoid implementation drift across scripts and tools.
- All changed Python files MUST pass `uv run ruff check --fix` and `uv run ruff format` before task completion.
- All changed Python files MUST pass pyright before task completion. Pyright is a dev dependency — invoke as `uv run python -m pyright <file>`. Do NOT use bare `pyright` or `uv run pyright` (the venv wrapper script has a fragile shebang that breaks on project moves).
- **`scripts/` vs `tools/`:** `scripts/` contains files run directly from the command line. `tools/` contains modules with functions called by scripts — purpose is to keep scripts focused and maintainable. Extraction into `tools/` does not require the code to be shared across multiple scripts.

## Temporary Files & Testing
- Use the `temp/` directory for all temporary files, scratchpad scripts, or one-off test files.
- The `temp/` directory is gitignored; do not commit files from this folder.
- Clean up temporary files in `temp/` once they are no longer needed for the current task.
- Do NOT create temporary or test files in the project root.

## Economy & Cost Management
- NEVER re-run batch LLM processing for trivial changes like filename dates or field labels. Use local text manipulation (e.g., regex, rename) instead.

## UI & Output
- Use `tools/printer.py` for all CLI script output (e.g., `pr.green()`, `pr.yes()`, `pr.no()`, `pr.warning()`). Avoid bare `print()` calls.

## Documentation
- When making a significant change to any pipeline (new flags, changed behaviour, new stages, renamed scripts), update the corresponding doc in `docs/`:
  - YouTube pipeline (English & Russian) → `docs/pipeline-youtube.md`
  - Quality control (transcription loop, semantic eval) → `docs/quality-control.md`
  - OpenAI batch pipeline → `docs/batch-pipeline.md`
- Include doc updates in the same commit as the code change.
