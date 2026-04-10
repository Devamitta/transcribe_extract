# Project Guide

## What It Is and Why
A local pipeline that converts MP3 Dhamma (Buddhist discourse) talks into raw Markdown transcripts using Apple MLX (local Whisper inference), then extracts core Dhamma points using the Gemini API. It helps a practitioner systematically process audio teachings and extract actionable Dhamma insights.

## Who It Is For
- **Primary:** A single practitioner using the tool personally to study Dhamma talks
- The user processes their own collection of Dhamma audio files

## One-Off or Ongoing
- **Ongoing:** The pipeline is designed to be run repeatedly as new talks are added
- The codebase will evolve as new features or improvements are needed

## What It Will Produce
- Raw Whisper transcripts in `/output/` (Markdown)
- Extracted Dhamma points in `/extracted/` (Markdown with metadata like tags, categories)
- Structured output with categorization and linking between related points

## How You'll Know It Worked
- Each MP3 in `/audio/` produces a corresponding extracted file in `/extracted/`
- Extracted files contain organized Dhamma points with metadata
- Pipeline runs without errors via `caffeinate -i nice -n 10 uv run python transcribe.py` then `uv run python extract_dhamma.py`