# Dhamma Transcriber & Extractor

A local pipeline that converts MP3 Dhamma talks into Markdown transcripts using MLX Whisper, then extracts core Dhamma points using an LLM (OpenRouter, Gemini, OpenAI, or DeepSeek).

> **Requires Apple Silicon (M1/M2/M3/M4).** MLX Whisper does not run on Intel Macs or Linux.

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

### 5. Initialize Directory Structure & Environment
```bash
./setup_folders.sh
```
Creates all required `audio/`, `video/`, `output/`, and `reports/` subdirectories, and generates a `.env` template in the project root. Run once after cloning.

### 6. Fill in `.env`

Open the generated `.env` and fill in the values you need:
- `PROVIDER` + the matching API key (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, etc.)
- `IMAGE_PROVIDER` for thumbnail generation
- `GDRIVE_FOLDER_ID_RU` / `GDRIVE_FOLDER_ID_EN` only if using Google Drive uploads (see [docs/upload-gdrive.md](docs/upload-gdrive.md))

---

## 1. Transcription

Converts raw audio into Markdown format, using context-specific Pali glossaries to improve accuracy.

| Scope | Command | Input | Output |
| :--- | :--- | :--- | :--- |
| **All** | `./transcribe.sh` | `audio/sangha/`, `audio/interview/`, `audio/dhamma/` | `output/transcribed/` |
| **Saṅgha** | `./transcribe.sh --context sangha` | `audio/sangha/` | `output/transcribed/sangha/` |
| **Interview** | `./transcribe.sh --context interview` | `audio/interview/` | `output/transcribed/interview/` |
| **Dhamma** | `./transcribe.sh --context dhamma` | `audio/dhamma/` | `output/transcribed/dhamma/` |

**Direct script:**
```bash
uv run python scripts/transcribe.py --input-dir <dir> --context <context>
```

**Options:**
- `--context`: `sangha`, `dhamma`, `vinaya`, `interview`, or `russian`
- `--test-run`: transcribe only the first file found

*Use `caffeinate -i nice -n 10` on macOS to prevent sleep and manage CPU priority.*

---

## 2. Dhamma Extraction Pipeline

Pāli correction → extraction → polishing. See [docs/pipeline-dhamma-extraction.md](docs/pipeline-dhamma-extraction.md).

---

## 3. YouTube Pipeline

Multi-stage pipeline for publishing Dhamma talks to YouTube and Google Drive (English and Russian). See [docs/pipeline-youtube.md](docs/pipeline-youtube.md).

**First-time setup:** configure OAuth credentials before running uploads — see [docs/upload-youtube.md](docs/upload-youtube.md) and [docs/upload-gdrive.md](docs/upload-gdrive.md).

**Quick start:**
```bash
./yt_run.sh --lang ru|en [folder] [--video-mode] [--dry-run]
```

---

## Project Structure

- `audio/` — Raw audio input (`sangha/`, `interview/`, `russian/`, `english/`)
- `video/` — Raw video input (`russian/`, `english/`)
- `output/` — All pipeline outputs (transcripts, extractions, upload assets)
- `scripts/` — Runnable pipeline scripts
- `tools/` — Shared modules imported by scripts
- `tests/` — Automated tests
- `docs/` — Pipeline documentation
- `reports/` — Semantic evaluation reports
- `reviews/` — YouTube metadata review files
- `log/` — Script run logs
- `temp/` — Scratch space (gitignored)
- `kamma/` — Project management and thread plans

---

## Pipeline Docs

| Pipeline | Doc |
| :--- | :--- |
| Dhamma extraction (Pāli correction, extraction, polishing) | [docs/pipeline-dhamma-extraction.md](docs/pipeline-dhamma-extraction.md) |
| YouTube pipeline (English & Russian) | [docs/pipeline-youtube.md](docs/pipeline-youtube.md) |
| YouTube upload OAuth setup | [docs/upload-youtube.md](docs/upload-youtube.md) |
| Google Drive upload setup | [docs/upload-gdrive.md](docs/upload-gdrive.md) |
| Quality control (transcription loop + semantic eval) | [docs/quality-control.md](docs/quality-control.md) |
| OpenAI Batch pipeline | [docs/batch-pipeline.md](docs/batch-pipeline.md) |
