# YouTube Pipeline

A multi-stage pipeline for processing Dhamma talks (English and Russian) for YouTube and Google Drive.

---

## One-Command Execution

```bash
./yt_run.sh [--lang ru|en] [--folder folder] [--from-export] [--gdrive] [--dry-run] [--context CONTEXT]
```

e.g. `./yt_run.sh --lang ru --gdrive`

| Flag | Description |
|---|---|
| `--lang ru\|en` | Optional. Sets language for review file selection. Defaults to `en`. |
| `--folder` | Optional. Specific folder in `input/` to scan. If omitted, scans `input/` root or subfolders. |
| `--from-export` | Skip transcription and metadata generation. Useful when resuming after metadata has already been reviewed. |
| `--gdrive` | Also upload to Google Drive (default: YouTube only). |
| `--dry-run` | Pass `--dry-run` to all upload steps. |
| `--context CONTEXT` | Whisper context tag. Defaults to `russian` (ru) or `dhamma` (en). English options: `dhamma`, `sangha`, `vinaya`, `interview`. |

The pipeline auto-detects **Video Mode** if `.mp4` files are found in the output directory after ingestion.

**Audio mode** pauses at two points for human review:
1. After metadata generation — to fill in recording dates and edit titles/descriptions.
2. After thumbnail generation — to review images before video creation begins.

---

## Folder & Review File Resolution

| Invocation | Scans | Output dirs | Review file |
|---|---|---|---|
| `./yt_run.sh` (no args) | `input/` root (subfolders preserved) | `output/audio/`, `output/video/` | `reviews/english_review.md` |
| `./yt_run.sh --lang en` | `input/english/` | `output/audio/english/` etc. | `reviews/english_review.md` |
| `./yt_run.sh --lang ru` | `input/russian/` | `output/audio/russian/` etc. | `reviews/russian_review.md` |
| `./yt_run.sh --lang en --folder interview` | `input/interview/` | `output/audio/interview/` etc. | `reviews/english_review.md` |
| `./yt_run.sh --lang ru --folder sangha` | `input/sangha/` | `output/audio/sangha/` etc. | `reviews/russian_review.md` |

Review file is always determined by `--lang` (defaulting to `en`), never by `--folder`.

---

## Stage 1: Ingest and Transcribe

### 1.1: Unified Ingestion
The pipeline begins by scanning `input/` or `input/<folder>/`.

```bash
uv run python scripts/yt_ingest_unified.py [--lang ru|en] [--folder <folder>] [--limit 5]
```

- **Video Files (`.mp4`, `.mkv`, `.mov`)**: Extracts audio to `output/audio/<folder>/` and moves the original video to `output/video/<folder>/`.
- **Non-MP3 Audio (`.wav`, `.m4a`, etc.)**: Converts to MP3 in `output/audio/<folder>/` and removes the original from `input/`.
- **MP3 Files**: Moves them to `output/audio/<folder>/`.

### 1.2: Transcription
Transcribe audio files using MLX Whisper.

```bash
caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
  --lang ru|en [--folder <folder>] \
  --context <context> \
  --chunk-seconds 20
```

- `--lang` resolves input to `output/audio/<lang-folder>/` and output to `output/transcribed/<lang-folder>/` automatically.
- `--folder` overrides the lang-derived subfolder name.

Input: MP3 files in `output/audio/<folder>/`
Output: Raw transcripts in `output/transcribed/<folder>/`

---

## Stage 2: Generate Metadata & Chapters

### 2.1: Metadata Suggestions
Generates titles and descriptions using the configured LLM provider.

```bash
uv run python scripts/yt_metadata.py --lang ru|en [--folder <folder>] [--limit 5]
```

Outputs are appended to `reviews/russian_review.md` or `reviews/english_review.md`.

### 2.2: YouTube Chapters
Generates AI chapter timestamps based on the transcript and appends them to the review file.

```bash
uv run python scripts/yt_chapters.py --lang ru|en [--folder <folder>] [--limit 5]
```

- **Placement Accuracy:** Transcribe with `--chunk-seconds 20` for best results.
- **Chapter Spacing:** Enforces a minimum of 2 minutes between chapters.

---

## Stage 2.5: Human Review

**REQUIRED STEP:** Open `reviews/english_review.md` or `reviews/russian_review.md` and:
1. **Fill in Recording Dates** for every talk (format: `DD-MM-YYYY`).
2. **Review and edit** suggested titles, descriptions, and tags.
3. **Approve** entries by setting `Approved: yes`.

The export script only processes entries where Recording Dates are filled and `Approved: yes`.

---

## Stage 3: Export and Video Creation

### 3.1: Export with Metadata
Renames source files and embeds reviewed metadata **in-place**.

```bash
uv run python scripts/yt_export.py --lang ru|en [--folder <folder>] [--video-mode]
```

- **Rename:** Renames files in `output/audio/` and `output/transcribed/` to `YYYY-MM-DD - Suggested Title`.
- **Embed:** Embeds metadata into the `.mp3` (and `.mp4` in video mode) using ffmpeg and a temporary file.

### 3.2: Generate AI Thumbnails (Audio Mode only)
Uses reviewed metadata to generate photorealistic thumbnails.

```bash
uv run python scripts/yt_image_gen.py --lang ru|en [--folder <folder>]
```

Output: `output/thumbnails/<folder>/`

### 3.3: Create MP4 Videos (Audio Mode only)
Combines thumbnails with MP3 audio files.

```bash
uv run python scripts/yt_video.py --lang ru|en [--folder <folder>]
```

- **Input:** `output/thumbnails/<folder>/` and `output/audio/<folder>/`
- **Output:** `output/video/<folder>/`

---

## Stage 4: Upload (YouTube & Google Drive)

### YouTube Upload
Uploads MP4s from `output/video/<folder>/`.

```bash
uv run python scripts/yt_upload.py --lang ru|en [--folder <folder>] [--dry-run]
```

### Google Drive Upload
Uploads MP4s and MP3s from their respective output directories.

```bash
uv run python scripts/gdrive_upload.py --lang ru|en [--folder <folder>] [--dry-run]
```
