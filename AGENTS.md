# Project Rules

dhamma_extract Project Rules. Apply these in addition to your baseline global instructions `~/.claude/CLAUDE.md`.

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