# Dhamma Transcriber & Extractor

A local pipeline that converts MP3 Dhamma talks into Markdown transcripts using MLX Whisper (Apple Silicon), then extracts core Dhamma points using Google Gemini API or OpenRouter.

---

## 0. Prerequisites & Installation

### 1. Install Homebrew
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install System Dependencies
```bash
brew install ffmpeg
```

### 3. Install `uv`
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 4. Setup Project & Dependencies
```bash
uv sync
```
*Run `uv sync` whenever you pull new changes.*

---

## 1. Transcription

Converts raw audio into Markdown format, using context-specific Pali glossaries to improve accuracy.

| Scope | Command | Input | Output |
| :--- | :--- | :--- | :--- |
| **All** | `./transcribe.sh` | `audio/sangha/` & `audio/interview/` | `output/transcribed/` |
| **Saṅgha** | `./transcribe-sangha.sh` | `audio/sangha/` | `output/transcribed/sangha/` |
| **Interview** | `./transcribe-interview.sh` | `audio/interview/` | `output/transcribed/interview/` |

**Direct script:**
```bash
uv run python scripts/transcribe.py --input-dir <dir> --output-dir <dir> --context <context>
```

**Options:**
- `--context`: `sangha`, `dhamma`, `vinaya`, `interview`, or `russian`
- `--test-run`: transcribe only the first file found

*Use `caffeinate -i nice -n 10` on macOS to prevent sleep and manage CPU priority.*

---

## 2. Pali Spelling Correction

Refines Pāli term spelling in transcripts using a consolidated glossary of ~155 terms.

**Process all transcripts:**
```bash
uv run python scripts/correct_pali.py
```

**Process a specific file or folder:**
```bash
uv run python scripts/correct_pali.py <filename_or_path>
```

Output: `output/corrected_pali/`, mirroring the input directory structure.

---

## 3. Dhamma Extraction

Extracts core Dhamma points, metadata, and tags from corrected transcripts.

```bash
uv run python scripts/extract_dhamma.py <filename>
```

**Environment setup** — create a `.env` file:
```bash
GEMINI_API_KEY_1=your_key_here
PROVIDER=google
```

---

## 4. Polishing

Rewrites extraction output into clean, readable English prose. Fixes fragmented sentences and non-native patterns while preserving all teaching points.

```bash
uv run python scripts/polish_extract.py output/extracted/interview/Talk.md
```

**Options:**
- `--dry-run`: see the prompt and input without calling the API
- `--output-dir <path>`: override default `output/polished/` destination

---

## Project Structure

- `audio/` — Raw audio files (`sangha/`, `interview/`, `russian/`, `english/`)
- `output/transcribed/` — Raw Markdown transcripts
- `output/corrected_pali/` — Pāli-corrected transcripts
- `output/extracted/` — Extracted Dhamma points
- `output/polished/` — Polished extraction output
- `scripts/` — Core pipeline scripts
- `kamma/` — Project management, thread plans, and quality loop tracking

---

## Pipeline Docs

| Pipeline | Doc |
| :--- | :--- |
| English YouTube pipeline | [docs/pipeline-english.md](docs/pipeline-english.md) |
| Russian YouTube pipeline | [docs/pipeline-russian.md](docs/pipeline-russian.md) |
| Quality control (transcription loop + semantic eval) | [docs/quality-control.md](docs/quality-control.md) |
| OpenAI Batch pipeline | [docs/batch-pipeline.md](docs/batch-pipeline.md) |
