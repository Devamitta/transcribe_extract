# Dhamma Transcriber & Extractor

A local pipeline that converts MP3 Dhamma talks into Markdown transcripts using MLX Whisper (Apple Silicon), then extracts core Dhamma points using Google Gemini API or OpenRouter.

## Directory Structure

- `/audio` - Place raw `.mp3` files here to transcribe
- `/output/transcribed` - Raw Whisper transcripts (Markdown)
- `/output/corrected_pali` - Pāli-corrected transcripts
- `/output/extracted` - Final extracted Dhamma points (Markdown with tags)

## CLI Usage — Run `transcribe` From Anywhere

Add the `scripts/cl` directory to your `PATH` so you can run `transcribe` from any terminal:

### 1. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Add `scripts/cl` to Your PATH

Add this line to your `~/.zshrc` (or `~/.bashrc`):

```bash
export PATH="/Users/deva/Documents/dps/transcribe_extract/scripts/cl:$PATH"
```

Then reload your shell: `source ~/.zshrc`

### 3. Run Transcription From Anywhere

```bash
transcribe
```

This resolves the project root automatically and runs the transcription pipeline.

## Quick Start

```bash
# Install dependencies
uv sync

# Transcription (MLX Whisper)
caffeinate -i nice -n 10 uv run python scripts/transcribe.py

# Pāli Correction
uv run python scripts/correct_pali.py

# Dhamma Extraction
uv run python scripts/extract_dhamma.py
```

## Environment Variables

Create a `.env` file with:

```bash
# Google Gemini (free tier - supports multiple keys for rotation)
GEMINI_API_KEY_1=your_key_here
GEMINI_API_KEY_2=your_key_here
# ... add more keys for rotation

# Or OpenRouter (paid)
OPENROUTER_API_KEY=your_key_here

# Which provider to use (google or openrouter)
PROVIDER=google
```

## Running on Specific Files

Process a single file instead of all files:

```bash
# Correct Pāli on specific file
uv run python scripts/correct_pali.py <filename>

# Extract Dhamma on specific file
uv run python scripts/extract_dhamma.py <filename>

# Examples
uv run python scripts/correct_pali.py test_3500.md
uv run python scripts/extract_dhamma.py output/corrected_pali/test_3500.md
```

## Test Mode

Use `--test` or `-t` flag to verify the pipeline runs without errors (smoke test only):

```bash
# Smoke test - uses a lighter/cheaper model, processes max 3 chunks
# Purpose: confirm the script runs end-to-end, NOT to evaluate output quality
uv run python scripts/correct_pali.py --test <filename (only name, not path)>
uv run python scripts/extract_dhamma.py --test <filename (only name, not path)>
```

**Do not use `--test` to evaluate output quality.** The lighter model produces degraded
results and is only useful for confirming the pipeline is functional (imports work,
API calls succeed, files are written).

To evaluate output quality, run the full model on one of the test files:

```bash
# Quality test - uses the full production model on a known test file <filename (only name, not path)>
uv run python scripts/extract_dhamma.py test_3500.md
uv run python scripts/extract_dhamma.py test_another_3500.md
```

## Model Configuration

Model lists are defined in `tools/provider.py`:

- **Gemini work models**: `gemini-2.5-flash`
- **Gemini test models**: `gemini-3.1-flash-lite-preview`
- **OpenRouter work models**: Free models (auto-rotates on failure)
- **OpenRouter test models**: Cheapest available

## List Available Models

```bash
# List Gemini models
uv run python tools/gemini.py

# List OpenRouter models (free only)
uv run python tools/openrouter.py

# List all OpenRouter models
uv run python tools/openrouter.py --all
```

## Scripts

- `scripts/transcribe.py` - Transcribe MP3 to Markdown using MLX Whisper
- `scripts/correct_pali.py` - Correct Pāli spellings using AI
- `scripts/extract_dhamma.py` - Extract Dhamma points with tagging

## Tools

- `tools/gemini.py` - Google Gemini API wrapper
- `tools/openrouter.py` - OpenRouter API wrapper  
- `tools/provider.py` - Unified provider hub (routes to correct API)