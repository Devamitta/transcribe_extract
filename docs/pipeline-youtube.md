# YouTube Pipeline

A multi-stage pipeline for processing Dhamma talks (English and Russian) for YouTube and Google Drive.

---

## One-Command Execution

```uv run bash yt_run.sh --lang ru|en [folder] [--video-mode] [--from-export] [--dry-run] [--context CONTEXT]
```

e.g. uv run bash yt_run.sh --lang ru russian --from-export --gdrive

| Flag | Description |
|---|---|
| `--lang ru\|en` | Required. Sets language for metadata, chapters, and thumbnails. |
| `folder` | Optional. Input subfolder under `audio/` (or `video/` in video mode). Defaults to `russian` (ru) or `english` (en). |
| `--video-mode` | Input is `.mp4` files. Ingests audio from video, embeds metadata back into mp4, then uploads. Skips thumbnail and video creation steps. |
| `--from-export` | Skip transcription and metadata generation. Useful when resuming after metadata has already been reviewed. |
| `--gdrive` | Also upload to Google Drive (default: YouTube only). |
| `--dry-run` | Pass `--dry-run` to all upload steps (both modes). |
| `--context CONTEXT` | Whisper context tag. Defaults to `russian` (ru) or `dhamma` (en). English options: `dhamma`, `sangha`, `vinaya`, `interview`. |

**Audio mode** pauses at two points for human review:
1. After metadata generation — to fill in recording dates and edit titles/descriptions.
2. After thumbnail generation — to review images before video creation begins.

Both modes end with YouTube and Google Drive uploads. Pass `--dry-run` to run those steps without actually uploading.

> All individual scripts accept `--lang ru|en`; omitting `--folder` then defaults to the lang-based subfolder (`ru→russian`, `en→english`).

---

## Stage 1: Ingest and Transcribe

### 1.1: Audio Ingestion & Conversion
Ensure all input audio is in MP3 format (required by Whisper).

**For Video Files (`--video-mode`):**
Extracts audio from `.mp4` files in `video/<folder>/` into `audio/<folder>/`:
```bash
uv run python scripts/yt_ingest.py --lang ru|en [--folder <folder>] --limit 5
```

**For Non-MP3 Audio Files (default):**
Converts any non-MP3 files in `audio/<folder>/` in-place:
```bash
uv run python scripts/yt_audio_convert.py --lang ru|en [--folder <folder>] --limit 5
```

**Common Options:**
- `--lang ru|en`: (Optional) Language shortcode. Sets default folder (`ru→russian`, `en→english`).
- `--folder NAME`: (Optional) Subfolder to process. If both `--lang` and `--folder` are absent, scans all subfolders.
- `--limit N`: Process only the first N files globally (across all target subfolders).

### 1.2: Transcription
Transcribe audio files using MLX Whisper. Use `--chunk-seconds 20` for finer YouTube chapter timestamps (default: 60):

```bash
caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
  --input-dir audio/<folder> \
  --output-dir output/transcribed/<folder> \
  --context <context> \
  --chunk-seconds 20
```

Input: MP3 files in `audio/<folder>/`
Output: Raw transcripts in `output/transcribed/<folder>/`

---

## Stage 2: Generate Metadata & Chapters

### 2.1: Metadata Suggestions
Generates titles and descriptions using the configured LLM provider.

```bash
uv run python scripts/yt_metadata.py --lang ru|en [--folder <folder>] --limit 5
```

**Options:**
- `--lang ru|en`: (Required) Language of the talk and prompts.
- `--folder NAME`: (Optional) Subfolder in `output/transcribed/` to process. Defaults to `russian`/`english` based on `--lang` when omitted. Supports subfolder traversal.
- `--limit N`: Process only the first N files globally.
- `--file <filename>`: Process a single file only (test mode)
- `--input-dir <path>`: Use an alternative transcript directory, e.g. `output/corrected_pali/<folder>` for Pali-corrected English transcripts.
- `--test`: Use provider test models

### 2.2: YouTube Chapters
Generates AI chapter timestamps based on the transcript and appends them to the review file.

```bash
uv run python scripts/yt_chapters.py --lang ru|en [--folder <folder>] --limit 5
```

**Default Mode:** By default, the script uses **paragraph mode**. It reads the full transcript and allows the LLM to select semantic topic transitions from all available paragraph timestamps.

- **Placement Accuracy:** For best results, transcribe with `--chunk-seconds 20` (default is 60). This gives the LLM finer-grained timestamps to choose from.
- **Density Check:** Transcripts with a median paragraph gap > 30 seconds are automatically skipped. This prevents "timestamp starvation" where chapters would be forced to snap to 1–3 minute intervals. Re-transcribe with `--chunk-seconds 20` to fix.
- **Chapter Spacing:** The script enforces a **minimum of 2–3 minutes between chapters**. If the LLM suggests chapters too close together, they are automatically merged or dropped.

**Options:**
- `--lang ru|en`: (Required) Language of the talk and prompts.
- `--folder NAME`: (Optional) Subfolder in `output/transcribed/` to process. Defaults to `russian`/`english` based on `--lang` when omitted. Supports subfolder traversal.
- `--limit N`: Process only the first N files globally.
- `--silence-mode`: (Experimental) Use ffmpeg silence detection to constrain chapter anchors.

### 2.3: Silence Mode (Experimental)

If paragraph mode is not producing the desired results, you can experiment with audio-based silence detection to force chapters onto real pauses.

**Diagnostic workflow:**
1. Run diagnostics on 1–2 representative talks:
   ```bash
   uv run python scripts/yt_chapters.py --lang ru|en [--folder <folder>] \
     --file "path/to/talk.md" \
     --silence-mode --debug --debug-log --diagnose-only
   ```
2. Inspect the debug log in `temp/yt_chapters_debug_<stem>.log`
3. Review the histogram of silence durations and per-stage anchor counts.
4. Adjust thresholds and re-run without `--diagnose-only`.

**Tuning flags (require --silence-mode):**
- `--silence-min-dur SEC`: Minimum silence duration (seconds) to count as a topic break. Default: `3.0`.
- `--silence-noise-db DB`: Noise floor (dB) below which audio counts as silent. Default: `-20`.
- `--snap-tolerance MIN`: Tolerance (minutes) for snapping LLM timestamps to anchor list. Default: `0.75`.
- `--debug`: Print diagnostics to console at every filter stage.
- `--debug-log`: Write full diagnostic trace to `temp/yt_chapters_debug_<stem>.log`.
- `--diagnose-only`: Run diagnostics but skip the LLM call.

---

## Stage 2.5: Human Review

**REQUIRED STEP:** Open `reviews/<folder>_review.md` and:
1. **Fill in Recording Dates** for every talk (format: `DD-MM-YYYY`)
2. **Review and edit** suggested titles and descriptions
3. **Approve** all entries before proceeding

The export script treats this file as the source of truth — it only processes entries where Recording Dates are filled.

---

## Stage 3: Export and Video Creation

### 3.1: Export with Metadata
Renames source audio and transcript files to `YYYY-MM-DD - Suggested Title`, then exports copies with embedded metadata.

```bash
uv run python scripts/yt_export.py --lang ru|en [--folder <folder>] --limit 5
```

- **Step 1 — Rename:** `audio/<folder>/*.mp3` and `output/transcribed/<folder>/*.md` → `YYYY-MM-DD - Suggested Title.{ext}`
- **Step 2 — Export:** copies renamed MP3s to `output/<folder>_audio/` with embedded metadata

**Options:**
- `--lang ru|en`: (Optional) Language shortcode. Sets default folder.
- `--folder NAME`: (Optional) Subfolder to process. If both absent, scans all subfolders.
- `--video-mode`: For video-input talks, embeds metadata into `.mp4` and moves to `output/<folder>_video_upload/`
- `--dry-run`: Preview planned renames only; skips export

### 3.2: Generate AI Thumbnails

**REQUIRED: review thumbnails before proceeding to video creation.**

Uses reviewed metadata to generate photorealistic thumbnails via OpenRouter FLUX.

```bash
uv run python scripts/yt_image_gen.py --lang ru|en [--folder <folder>] --limit 5
```

**Options:**
- `--lang ru|en`: (Required) Language of the talk and prompts.
- `--folder NAME`: (Optional) Subfolder name (e.g. 'russian'). Defaults to lang-based folder when omitted.

### 3.3: Create MP4 Videos
Combines the generated thumbnails with the original MP3 audio files using `ffmpeg`.

```bash
uv run python scripts/yt_video.py --lang ru|en [--folder <folder>] --limit 5
```

- **Input:** `output/<folder>_thumbnails/` and `output/<folder>_audio/`
- **Output:** `output/<folder>_youtube/`

**Options:**
- `--lang ru|en`: (Optional) Language shortcode. Sets default folder.
- `--folder NAME`: (Optional) Subfolder to process. If both absent, scans all subfolders.
- `--limit N`: Process only the first N talks globally.

---

## Stage 4: Upload (YouTube & Google Drive)

Automates the upload of MP4s to YouTube and MP4+MP3 to Google Drive.

**See `output/UPLOAD_SETUP.md` first** for OAuth credential setup.

### YouTube Upload

```bash
# Dry-run: verify description format and metadata match without uploading
uv run python scripts/yt_upload.py --lang ru|en [--folder <folder>] --dry-run

# Upload approved videos
uv run python scripts/yt_upload.py --lang ru|en [--folder <folder>]
```

**Options:**
- `--lang ru|en`: (Required) Language shortcode.
- `--folder NAME`: (Optional) Subfolder name (e.g. 'russian'). Defaults to lang-based folder when omitted.

- **Tokens:** Uses `youtube_token_ru.json` or `youtube_token_en.json` based on `--lang`.
- **History:** `output/youtube_history.json` uses language-scoped sections (`ru`, `en`) to track uploads separately per language.

### Google Drive Upload

```bash
uv run python scripts/gdrive_upload.py --lang ru|en --folder <folder>
```

- **Folder ID:** Reads `GDRIVE_FOLDER_ID_RU` or `GDRIVE_FOLDER_ID_EN` from `.env`.
- **History:** `output/gdrive_history.json` uses nested sections (`ru.video`, `ru.audio`, `en.video`, `en.audio`) to track uploads separately per language and type.
