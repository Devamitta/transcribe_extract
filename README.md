# Dhamma Transcriber & Extractor

A local pipeline that converts MP3 Dhamma talks into Markdown transcripts using MLX Whisper, then extracts core Dhamma points using an LLM.

> **Requires Apple Silicon (M1/M2/M3/M4).** MLX Whisper does not run on Intel Macs or Linux.

---

## Setup

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
./setup_folders.sh
```

**Fill in `.env`** (created by `setup_folders.sh`):
- API keys — `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, or `DEEPSEEK_API_KEY`; `gemini-cli` and `antigravity-cli` use local CLI auth instead
- **Provider/model routing is configured in `tools/ai_models.json`, not `.env`.** Requests follow the cross-provider `default_models` fallback order there. To restrict routing to a single provider, set `PROVIDER=<name>` on the command line for that run (e.g. `PROVIDER=agy uv run ...`); a `PROVIDER` value in `.env` is ignored.
- **Bio links:** set `BIO_EN` and `BIO_RU` to append a speaker bio to YouTube descriptions. Leave empty (default) for no bio.

**YouTube OAuth** (first-time only): [docs/upload-youtube.md](docs/upload-youtube.md)

---

## Transcription

Drop audio files (MP3, WAV, M4A, QTA, etc.) into `input/sangha/` (or any other subfolder in `input/`) and run:

```bash
./scripts/cl/transcribe-correct sangha
```

If run without a folder name, it will list available folders and provide instructions.

Output: `output/corrected_pali/sangha/`

Full reference: [docs/transcription.md](docs/transcription.md)

---

## YouTube Pipeline

Drop MP3 or MP4 files into `input/` and run:

```bash
./yt_run.sh --name "Tissa Thero"
```

`--name` sets the speaker name used for metadata context and artist metadata. Custom names are appended to generated review titles, except configured no-suffix names such as Ariyadhammika Bhikkhu.

The pipeline pauses three times:
1. Optionally add chapter names to the review file. Press Enter to continue.
2. Open `reviews/english_review.md` — fill in recording dates (`DD-MM-YYYY`), review titles/descriptions, set `Approved: yes`. Press Enter.
3. Review generated thumbnails in `output/thumbnails/`. Press Enter (or `r` to regenerate).

Done — MP4 videos are created and uploaded to YouTube.

Add `--gdrive` to also upload MP4/MP3 backups to Google Drive. Video files go under `video/`; audio files go under `audio/`. `Selected Playlist` is the only field that can add a subfolder inside those base folders. If multiple playlists are selected, the Drive upload asks which single subfolder to use. If `Selected Playlist` is blank, no extra subfolder is used.

Full reference: [docs/pipeline-youtube.md](docs/pipeline-youtube.md)

---

## Other Pipelines

| Pipeline | Doc |
| :--- | :--- |
| Dhamma extraction | [docs/pipeline-dhamma-extraction.md](docs/pipeline-dhamma-extraction.md) |
| Google Drive upload | [docs/upload-gdrive.md](docs/upload-gdrive.md) |
| Quality control | [docs/quality-control.md](docs/quality-control.md) |
| OpenAI Batch pipeline | [docs/batch-pipeline.md](docs/batch-pipeline.md) |
