# Universal YouTube Pipeline (Russian)

A multi-stage pipeline for processing Russian Dhamma talks for YouTube and Google Drive.

---

## One-Command Execution

The easiest way to run the entire pipeline (from audio to video) is using the shell script:

```bash
./yt_run_russian.sh [folder]
```

Default folder is `russian`. The script will stop after generating metadata to allow for human review.

---

## Stage 1: Ingest and Transcribe

### 1.1: Audio Ingestion & Conversion
Ensure all input audio is in MP3 format (required by Whisper).

**For Video Files:**
If starting with `.mp4` video files, extract the audio first:
```bash
uv run python scripts/yt_ingest.py --folder russian --limit 5
```

**For Non-MP3 Audio Files:**
This script converts any non-MP3 files in the folder in-place:
```bash
uv run python scripts/yt_audio_convert.py --folder russian --limit 5
```

**Common Options:**
- `--limit N`: Process only the first N files globally (across all target subfolders).

### 1.2: Transcription
Transcribe audio files using MLX Whisper. Use `--chunk-seconds 30` for finer YouTube chapter timestamps (default: 60):

```bash
caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
  --input-dir audio/russian \
  --output-dir output/transcribed/russian \
  --context russian \
  --chunk-seconds 30
```

Input: MP3 files in `audio/russian/`
Output: Raw transcripts in `output/transcribed/russian/`

---

## Stage 2: Generate Metadata & Chapters

### 2.1: Metadata Suggestions
Generates Russian titles and descriptions using the configured LLM provider.

```bash
uv run python scripts/yt_metadata.py --lang ru --folder russian --limit 5
```

**Options:**
- `--lang ru|en`: (Required) Language of the talk and prompts
- `--folder NAME`: Subfolder in `output/transcribed/` to process. **Supports subfolder traversal** (finds `.md` files in all subdirectories).
- `--limit N`: Process only the first N files globally.
- `--file <filename>`: Process a single file only (test mode)
- `--test`: Use provider test models

### 2.2: YouTube Chapters
Generates AI chapter timestamps based on the transcript and appends them to the review file.

```bash
uv run python scripts/yt_chapters.py --lang ru --folder russian --limit 5
```

**Options:**
- `--folder NAME`: Subfolder in `output/transcribed/` to process. **Supports subfolder traversal**.
- `--limit N`: Process only the first N files globally.

**Chapter Spacing:** The script enforces a **minimum of 2–3 minutes between chapters**. If the LLM suggests chapters too close together, they are automatically dropped with a warning. This ensures chapters are meaningful viewing markers, not micro-segments.

---

## Stage 2.5: Human Review

**REQUIRED STEP:** Open `output/russian_review_YYYY-MM-DD.md` and:
1. **Fill in Recording Dates** for every talk (format: `DD-MM-YYYY`)
2. **Review and edit** suggested titles and descriptions
3. **Approve** all entries before proceeding

The export script treats this file as the source of truth — it only processes entries where Recording Dates are filled.

---

## Stage 3: Export and Video Creation

### 3.1: Export with Metadata
Renames source audio and transcript files to `YYYY-MM-DD - Suggested Title`, then exports copies with embedded metadata.

```bash
uv run python scripts/yt_export.py --folder russian --limit 5
```

- **Step 1 — Rename:** `audio/russian/*.mp3` and `output/transcribed/russian/*.md` → `YYYY-MM-DD - Suggested Title.{ext}`
- **Step 2 — Export:** copies renamed MP3s to `output/russian_audio/` with embedded metadata

**Options:**
- `--limit N`: Process only the first N dated items globally.
- `--video-mode`: For video-input talks, embeds metadata into `.mp4` and moves to `output/russian_video_upload/`
- `--dry-run`: Preview planned renames only; skips export

### 3.2: Generate AI Thumbnails
Uses reviewed metadata to generate photorealistic thumbnails via OpenRouter FLUX.

```bash
IMAGE_PROVIDER=openrouter uv run python scripts/yt_image_gen.py --lang ru --folder russian --limit 5
```

**Options:**
- `--limit N`: Process only the first N approved talks globally.

### 3.3: Create MP4 Videos
Combines the generated thumbnails with the original MP3 audio files using `ffmpeg`.

```bash
uv run python scripts/yt_video.py --folder russian --limit 5
```

- **Input:** `output/russian_thumbnails/` and `output/russian_audio/`
- **Output:** `output/russian_youtube/`

**Options:**
- `--limit N`: Process only the first N talks globally.

---

## Stage 4: Upload (YouTube & Google Drive)

Automates the upload of MP4s to YouTube and MP4+MP3 to Google Drive.

**See `output/UPLOAD_SETUP.md` first** for OAuth credential setup.

### YouTube Upload

```bash
# Dry-run: verify description format and metadata match without uploading
uv run python scripts/yt_upload.py --lang ru --folder russian --dry-run

# Upload approved videos
uv run python scripts/yt_upload.py --lang ru --folder russian
```

- **Tokens:** Uses `youtube_token_ru.json` or `youtube_token_en.json` based on `--lang`.
- **History:** `output/youtube_history.json` uses language-scoped sections (`ru`, `en`) to track uploads separately per language.

### Google Drive Upload

```bash
uv run python scripts/gdrive_upload.py --lang ru --folder russian
```

- **Folder ID:** Reads `GDRIVE_FOLDER_ID_RU` or `GDRIVE_FOLDER_ID_EN` from `.env`.
- **History:** `output/gdrive_history.json` uses nested sections (`ru.video`, `ru.audio`, `en.video`, `en.audio`) to track uploads separately per language and type.
