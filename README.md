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
Creates all required `input/`, `video/`, `output/`, and `reports/` subdirectories, and generates a `.env` template in the project root. Run once after cloning.

### 6. Fill in `.env`

Open the generated `.env` and fill in the values you need:
- `PROVIDER` + the matching API key (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, etc.)
- `IMAGE_PROVIDER` for thumbnail generation
- `GDRIVE_FOLDER_ID_RU` / `GDRIVE_FOLDER_ID_EN` only if using Google Drive uploads (see [docs/upload-gdrive.md](docs/upload-gdrive.md))

---

## 1. Transcription

Drop MP3s into `input/sangha/` and run:

```bash
./scripts/cl/transcribe-sangha
```

Transcribes with Saṅgha Pali vocabulary, then runs Pali correction. Output: `output/transcribed/sangha/`.

Full reference (all contexts, flags, direct script): [docs/transcription.md](docs/transcription.md).

---

## 2. YouTube Pipeline

Multi-stage pipeline for publishing Dhamma talks to YouTube and Google Drive (English and Russian). See [docs/pipeline-youtube.md](docs/pipeline-youtube.md).

**First-time setup:** configure OAuth credentials before running uploads — see [docs/upload-youtube.md](docs/upload-youtube.md) and [docs/upload-gdrive.md](docs/upload-gdrive.md).

**Quick run:**

Drop files into `input/` and run:
```bash
./yt_run.sh --name "Tissa Thero"
```

The pipeline auto-detects audio vs video from the file extension.

**Audio mode** (`.mp3` input) — ingest → transcribe → metadata:
1. **Pause 1** — optionally add chapter names to the review file before AI generates timestamps. Press Enter to continue.
2. **Pause 2** — open `reviews/english_review.md`: fill in recording dates (`DD-MM-YYYY`), review titles/descriptions, set `Approved: yes`. Press Enter.
3. **Pause 3** — review generated thumbnails in `output/thumbnails/`. Press Enter (or `r` to regenerate).
4. **Done** — MP4 videos are created and uploaded to YouTube.

**Video mode** (`.mp4` input) — ingest → transcribe → metadata:
1. **Pause 1** — optionally add chapter names. Press Enter.
2. **Pause 2** — fill dates, review metadata, approve. Press Enter.
3. **Done** — videos are uploaded directly (no thumbnail step). Add `--cover` to also generate and set cover thumbnails.

Add `--gdrive` to either mode to also upload to Google Drive.

Full flag reference and per-stage details: [docs/pipeline-youtube.md](docs/pipeline-youtube.md).

---

## 3. Dhamma Extraction Pipeline

Pāli correction → extraction → polishing. See [docs/pipeline-dhamma-extraction.md](docs/pipeline-dhamma-extraction.md).

---

## Project Structure

- `input/` — Raw input files (`sangha/`, `interview/`, `russian/`, `english/`)
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
| Transcription (all options, contexts, hallucination filter) | [docs/transcription.md](docs/transcription.md) |
| YouTube pipeline (English & Russian) | [docs/pipeline-youtube.md](docs/pipeline-youtube.md) |
| YouTube upload OAuth setup | [docs/upload-youtube.md](docs/upload-youtube.md) |
| Google Drive upload setup | [docs/upload-gdrive.md](docs/upload-gdrive.md) |
| Dhamma extraction (Pāli correction, extraction, polishing) | [docs/pipeline-dhamma-extraction.md](docs/pipeline-dhamma-extraction.md) |
| Quality control (transcription loop + semantic eval) | [docs/quality-control.md](docs/quality-control.md) |
| OpenAI Batch pipeline | [docs/batch-pipeline.md](docs/batch-pipeline.md) |
