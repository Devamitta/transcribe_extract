# Universal YouTube Pipeline (English)

A multi-stage pipeline for processing English Dhamma talks for YouTube and Google Drive.

---

## One-Command Execution

The easiest way to run the entire pipeline (from audio to video) is using the shell script:

```bash
./yt_run_english.sh [folder]
```

Default folder is `english`. The script will stop after generating metadata to allow for human review.

---

## Stage 1: Ingest and Transcribe

### 1.1: Audio Ingestion & Conversion
Ensure all input audio is in MP3 format (required by Whisper).

**For Video Files:**
If starting with `.mp4` video files, extract the audio first:
```bash
uv run python scripts/yt_ingest.py --folder english --limit 5
```

**For Non-MP3 Audio Files:**
This script converts any non-MP3 files in the folder in-place:
```bash
uv run python scripts/yt_audio_convert.py --folder english --limit 5
```

**Common Options:**
- `--limit N`: Process only the first N files globally (across all target subfolders).

### 1.2: Transcription
Transcribe audio files using MLX Whisper.

```bash
caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
  --input-dir audio/english \
  --output-dir output/transcribed/english \
  --context dhamma \
  --chunk-seconds 30
```

Input: MP3 files in `audio/english/`
Output: Raw transcripts in `output/transcribed/english/`

---

## Stage 2: Generate Metadata & Chapters

### 2.1: Metadata Suggestions
Generates English titles and descriptions using Gemini.

```bash
uv run python scripts/yt_metadata.py --lang en --folder english --limit 5
```

**Options:**
- `--lang ru|en`: (Required) Language of the talk and prompts
- `--folder NAME`: Subfolder in `output/transcribed/` to process. **Supports subfolder traversal** (finds `.md` files in all subdirectories).
- `--limit N`: Process only the first N files globally.
- `--input-dir <path>`: If you want to use corrected Pali transcripts, use `--input-dir output/corrected_pali/english`

### 2.2: YouTube Chapters
Generates AI chapter timestamps based on the transcript and appends them to the review file.

```bash
uv run python scripts/yt_chapters.py --lang en --folder english --limit 5
```

**Options:**
- `--folder NAME`: Subfolder in `output/transcribed/` to process. **Supports subfolder traversal**.
- `--limit N`: Process only the first N files globally.

**Chapter Spacing:** The script enforces a **minimum of 2–3 minutes between chapters**. If the LLM suggests chapters too close together, they are automatically dropped with a warning. This ensures chapters are meaningful viewing markers, not micro-segments.

---

## Stage 2.5: Human Review

**REQUIRED STEP:** Open `output/english_review_YYYY-MM-DD.md` and:
1. **Fill in Recording Dates** for every talk (format: `DD-MM-YYYY`)
2. **Review and edit** suggested titles and descriptions
3. **Approve** all entries before proceeding

---

## Stage 3: Export and Video Creation

### 3.1: Export with Metadata
Renames source audio and transcript files to `YYYY-MM-DD - Suggested Title`, then exports copies with embedded metadata to `output/english_audio/`.

```bash
uv run python scripts/yt_export.py --folder english --limit 5
```

**Options:**
- `--limit N`: Process only the first N dated items globally.

### 3.2: Generate AI Thumbnails
Generates photorealistic thumbnails via OpenRouter FLUX.

```bash
IMAGE_PROVIDER=openrouter uv run python scripts/yt_image_gen.py --lang en --folder english --limit 5
```

**Options:**
- `--limit N`: Process only the first N approved talks globally.

### 3.3: Create MP4 Videos
Combines the generated thumbnails with the original MP3 audio files using `ffmpeg`.

```bash
uv run python scripts/yt_video.py --folder english --limit 5
```

- **Input:** `output/english_thumbnails/` and `output/english_audio/`
- **Output:** `output/english_youtube/`

**Options:**
- `--limit N`: Process only the first N talks globally.

---

## Stage 4: Upload (YouTube & Google Drive)

Automates the upload of MP4s to YouTube and MP4+MP3 to Google Drive.

### YouTube Upload

```bash
uv run python scripts/yt_upload.py --lang en --folder english
```

- **Tokens:** Uses `youtube_token_en.json` (requires separate OAuth setup).

### Google Drive Upload

```bash
uv run python scripts/gdrive_upload.py --lang en --folder english
```

- **Folder ID:** Reads `GDRIVE_FOLDER_ID_EN` from `.env`.
