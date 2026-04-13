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
- `/audio`: Raw `.mp3` files to process
- `/output`: Raw Whisper transcripts (Markdown)
- `/extracted`: Final extracted Dhamma points (Markdown with metadata)

## Pipeline Commands
1. Transcription: `caffeinate -i nice -n 10 uv run python transcribe.py`
2. Extraction: `uv run python extract_dhamma.py`

## Code Quality
- All changed Python files MUST pass `uv run ruff check --fix` and `uv run ruff format` before task completion.

## Temporary Files & Testing
- Use the `temp/` directory for all temporary files, scratchpad scripts, or one-off test files.
- The `temp/` directory is gitignored; do not commit files from this folder.
- Clean up temporary files in `temp/` once they are no longer needed for the current task.
- Do NOT create temporary or test files in the project root.

## Economy & Cost Management
- NEVER re-run batch LLM processing for trivial changes like filename dates or field labels. Use local text manipulation (e.g., regex, rename) instead.
