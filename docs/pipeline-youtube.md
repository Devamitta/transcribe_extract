# YouTube Pipeline

A multi-stage pipeline for processing Dhamma talks (English and Russian) for YouTube and Google Drive.

---

## One-Command Execution

```bash
./yt_run.sh [--lang ru|en] [--folder folder] [--name NAME] [--from-export] [--video-mode] [--cover] [--gdrive] [--dry-run] [--force] [--context CONTEXT] [--limit N]
```

e.g. `./yt_run.sh --lang ru --gdrive`

| Flag | Description |
|---|---|
| `--lang ru\|en` | Optional. Sets language for review file selection. Defaults to `en`. |
| `--folder` | Optional. Specific folder in `input/` to scan. If omitted, scans `input/` root or subfolders. |
| `--name NAME` | Optional. Override the speaker/artist name used for metadata context and embedded artist metadata. The lang-derived default speaker is appended to generated titles when `--name` is omitted; custom names are also appended, except configured no-suffix names such as Ariyadhammika Bhikkhu. |
| `--from-export` | Deprecated compatibility flag. Normal runs are resumable: rerun `yt_run.sh` and completed stages are skipped. |
| `--video-mode` | Enables video mode. Must be set explicitly — the pipeline no longer auto-detects from .mp4 files in input/. A mismatch prompt appears if input and flag disagree. |
| `--cover` | Generate AI thumbnails/covers via `yt_image_gen.py` + `yt_cover_gen.py`. In video mode, thumbnail generation is skipped by default and only runs with this flag. **Note:** input images (PNG/JPG in `input/`) are always copied to both `output/thumbnails/` and `output/covers/` regardless of this flag. |
| `--gdrive` | Also upload to Google Drive (default: YouTube only). |
| `--dry-run [file]` | Trace the full pipeline without real processing. Optional stub file (e.g. `test.mp4`) is created in `input/` (or `input/<lang_folder>/` when `--lang` is set) so mode detection and path routing work end-to-end. All stubs and the stub review entry are cleaned up automatically at the end. |
| `--force` | Bypass YouTube upload-history safety skips in supported stages. Existing output-file existence checks still apply unless a script explicitly supports regenerating that output. |
| `--context CONTEXT` | Whisper context tag. Defaults to `russian` (ru) or `dhamma` (en). English options: `dhamma`, `sangha`, `vinaya`, `interview`. |
| `--limit N` | Optional. Cap all file-processing stages to the first N files. Passed through to every script that supports it (ingest, transcribe, metadata, chapters, export, thumbnail, video, upload, gdrive). Works in both normal and dry-run mode. |

Video Mode is enabled explicitly via the --video-mode flag. If video files are present in input/ but the flag is not set, the pipeline will prompt before continuing in audio mode.

### Dry-run mode

`--dry-run [stub_file]` runs the full pipeline without any real processing, API calls, or file mutations. Every stage prints its configured `input → output` paths for verification.

```bash
./yt_run.sh --lang ru --dry-run test.mp4   # traces Russian video-mode pipeline → stub at input/russian/test.mp4
./yt_run.sh --lang en --dry-run test.mp3   # traces English audio-mode pipeline → stub at input/english/test.mp3
./yt_run.sh --dry-run russian/test.mp4     # explicit subdir stub (no --lang required)
./yt_run.sh --dry-run                      # shows configured paths only (no stub)
```

**With a stub file**, the zero-byte file is created in `input/<path>` so the extension-based mode detection (`*.mp4` → video mode) works correctly. When `--lang` is set and the stub has no explicit subdir, the file is placed inside `input/<lang_folder>/` automatically. Each stage propagates the stub to its own output directory so the next stage can find it. At the end, all stubs and the temporary review entry (marked `[DRY_RUN]`) are removed automatically.

Use this to verify that a new input file would be routed through the correct folders before committing to a real run.

**Audio mode** pauses at three points for human review:
1. Before chapter generation — to optionally pre-fill chapter names in the review file.
2. After chapter/metadata generation — to fill in recording dates and edit titles/descriptions.
3. After thumbnail/cover generation — to review images (enter `r` to re-run with confirmation, Enter to continue).

The review pauses are conditional. If a rerun finds that no new metadata, chapter blocks, thumbnails, or covers were generated, those prompts are skipped.

### Resumable reruns

`yt_run.sh` is resumable by default. If a run is stopped, rerun the same command; each stage scans the current output state and skips completed work:

- transcription skips MP3s with existing transcripts
- metadata skips transcripts already present in the review file
- chapters skip entries that already have timed chapters
- export keeps reviewed titles canonical and renames files to `YYYY-MM-DD - Suggested Title`
- thumbnails, covers, and videos skip existing output files
- YouTube and Google Drive uploads skip files already marked uploaded in their history files

Temporary logs are no longer used to define normal real-run scope. They are still used for transcription duration verification, dry-run propagation, export title-sync paths, and selective thumbnail/cover reruns.

Filename matching is Unicode-normalized to NFC for comparisons and history lookups. This prevents duplicate work when macOS presents decomposed filenames for Pāli diacritics or Russian characters such as `Ё`, `ё`, `Й`, and `й`.

---

## Folder & Review File Resolution

| Invocation | Scans | Output dirs | Review file |
|---|---|---|---|
| `./yt_run.sh` (no args, root files in `input/`) | `input/` root | `output/audio/`, `output/video/` | `reviews/english_review.md` |
| `./yt_run.sh` (no args, subfolder in `input/`) | `input/<subfolder>/` (auto-detected subfolder mode) | `output/audio/<subfolder>/` etc. | `reviews/english_review.md` |
| `./yt_run.sh --lang en` | `input/english/` | `output/audio/english/` etc. | `reviews/english_review.md` |
| `./yt_run.sh --lang ru` | `input/russian/` | `output/audio/russian/` etc. | `reviews/russian_review.md` |
| `./yt_run.sh --lang en --folder interview` | `input/interview/` | `output/audio/interview/` etc. | `reviews/english_review.md` |
| `./yt_run.sh --lang ru --folder sangha` | `input/sangha/` | `output/audio/sangha/` etc. | `reviews/russian_review.md` |

Review file is always determined by `--lang` (defaulting to `en`), never by `--folder`.

**Auto-detection (no `--lang`, no `--folder`):** If `input/` has root-level media files, the pipeline operates in root mode. If `input/` has no root-level media but contains exactly one subfolder with media, that subfolder is used only for file routing. Folder names are not YouTube playlist names.

---

## Stage 1: Ingest and Transcribe

### 1.1: Unified Ingestion
The pipeline begins by scanning `input/` or `input/<folder>/`.

```bash
uv run python scripts/yt_ingest_unified.py [--lang ru|en] [--folder <folder>] [--limit 5] [--cover]
```

- **Video Files (`.mp4`, `.mkv`, `.mov`, `.mpeg`, `.mpg`)**: Converted to `.mp4` and saved to `output/video/<folder>/`. If no same-stem audio input exists, an MP3 is extracted from the video into `output/audio/<folder>/`. If a same-stem audio input is present in the same scanned `input/` folder (for example `test.wav` or `test.mp3` beside `test.mp4`), the video audio is not extracted; the separate audio file is moved or converted by the normal audio handling and becomes `output/audio/<folder>/test.mp3`.
- **Images (.png, .jpg, .jpeg)**: Converted to JPG and moved to output/thumbnails/<folder>/. If --cover is set, also copied to output/covers/<folder>/.
- **Non-MP3 Audio (`.wav`, `.m4a`, etc.)**: Converts to MP3 in `output/audio/<folder>/` and removes the original from `input/`.
- **MP3 Files**: Moves them to `output/audio/<folder>/`.

After ingest, `yt_review_dedup.py` runs a dedup check to resolve any duplicate recording dates in the review file before transcription begins.

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

### 1.3: Duration Verification

```bash
uv run python scripts/verify_duration.py \
  --audio-dir output/audio/<folder>/ \
  --transcript-dir output/transcribed/<folder>/ \
  --created-log <path>
```

Checks that the last Whisper timestamp in each transcript is within 120 s of the actual audio duration, flagging potential truncations. `--created-log` receives the path written by `transcribe.py` in the same run — only the files just produced are checked (no timestamp guessing). Failures print a warning but do not abort the pipeline.

---

## Stage 2: Generate Metadata & Chapters

### 2.1: Metadata Suggestions
Generates titles and descriptions using the configured LLM provider.

```bash
uv run python scripts/yt_metadata.py [--lang ru|en] [--folder <folder>] [--name NAME] [--limit 5] [--video-mode] [--created-log <path>]
```

- A bio link is appended to the description when the BIO_EN or BIO_RU environment variable (set in .env) is non-empty. Language selection: --lang ru → BIO_RU, otherwise BIO_EN. Leave empty for no bio. See setup_folders.sh for template.
- `--video-mode` marks new review entries with `**Media:** video` instead of the default `audio`. This field is used downstream by `yt_cover_gen.py` to filter which entries receive a cover thumbnail.
- `--created-log` records sources that received new review entries. Normal `yt_run.sh` reruns do not use this as the pipeline scope; dry-runs still use it to keep stub processing isolated.
- New review entries include playlist controls:
  - `**Channel Playlist Overview:** Meditation, Personal`
  - `**Selected Playlist:** Meditation, Personal`
- Edit `Selected Playlist` during review. Separate multiple existing playlist names with commas or semicolons, e.g. `Meditation, Personal` or `Meditation; Personal`.
- Default descriptions are requested as 5-7 sentences with no bullets. If `--name` contains `Ariyadhammika`, descriptions may be up to 15 sentences with no bullets.

Outputs are appended to `reviews/russian_review.md` or `reviews/english_review.md`.

After the user fills in dates and edits the review file, `yt_review_dedup.py` runs a title-similarity check across all review entries. Pairs with ≥ 90% title similarity are flagged as potential duplicates — regardless of recording date. Entries with the same date but different titles are not flagged.

### 2.2: YouTube Chapters
Generates AI chapter timestamps based on the transcript and appends them to the review file.

```bash
uv run python scripts/yt_chapters.py --lang ru|en [--folder <folder>] [--limit 5] [--source-log <path>]
```

- **Placement Accuracy:** Transcribe with `--chunk-seconds 20` for best results.
- **Chapter Spacing:** Enforces a minimum of 2 minutes between chapters. Talks shorter than 3 minutes are skipped entirely.
- **LLM retries:** Empty responses, timeouts, and provider errors are retried for the same transcript up to 3 total attempts. If all attempts fail, `yt_chapters.py` exits non-zero so `yt_run.sh` stops at that file.
- Direct `--source-log` runs can scope chapter generation manually. Normal `yt_run.sh` reruns scan for entries that still need chapters.

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
uv run python scripts/yt_export.py --lang ru|en [--folder <folder>] [--name NAME] [--video-mode] [--sync-titles] [--source-log <path>]
```

- **Rename:** Renames files in `output/audio/` and `output/transcribed/` to `YYYY-MM-DD - Suggested Title`. Also renames matching .jpg files in output/thumbnails/<folder>/ and output/covers/<folder>/ to keep image filenames in sync.
- **Embed:** Embeds metadata into the `.mp3` (and `.mp4` in video mode) using ffmpeg and a temporary file.
- **Title sync:** `--sync-titles` only reruns the rename/source-line sync from the review file and skips ffmpeg metadata embedding. Use it after editing `**Suggested Title:**` on already-exported entries.
- **Source scoping:** Direct `yt_export.py` runs process the approved review file unless `--source-log` is supplied. Normal `yt_run.sh` reruns rely on per-stage skip checks instead of current-run scoping.
- **Upload-history safety:** Export skips entries already marked uploaded in YouTube history before any rename, checking both the current source filename and the computed final reviewed-title filename.

### 3.2: Generate AI Thumbnails (Audio Mode; or Video Mode with `--cover`)
Uses reviewed metadata to generate photorealistic base thumbnails via FLUX.

```bash
uv run python scripts/yt_image_gen.py --lang ru|en [--folder <folder>] [--source-log <path>]
```

Output: `output/thumbnails/<folder>/`

The pipeline pauses here for visual review. Pressing `r` lists the files created in this image-generation pass and lets you remove selected numbers/ranges, or `all`; only removed images are regenerated because existing thumbnails are skipped. Pressing Enter continues.

### 3.3: Generate Cover Thumbnails (`--cover` only)
Composites a text overlay (title, teacher name, AI-generated highlights) onto the base thumbnail to create a YouTube cover image.

```bash
uv run python scripts/yt_cover_gen.py --lang ru|en [--folder <folder>] [--limit N] [--dry-run] [--list-fonts] [--source-log <path>]
```

- **Input:** `output/thumbnails/<folder>/` (FLUX images from 3.2)
- **Output:** `output/covers/<folder>/`
- Processes approved entries from the review file. Normal `yt_run.sh` reruns skip existing covers and uploaded videos.
- Cover titles force new lines at common separators such as `:`, `|`, `/`, `;`, `,`, `.`, `?`, `!`, bullets, and spaced dashes.
- `--list-fonts` generates paginated font preview sheets (`temp/font_preview_<lang>_01.png`, …) and an index (`temp/font_list_<lang>.md`), then exits — useful for picking a font before the first run.
- Font and overlay parameters are configurable via `.env` (`COVER_FONT_PATH`, `COVER_RU_FONT_PATH`, `COVER_GRADIENT_HEIGHT_PCT`, etc.); all have sensible defaults and the script works with no `.env` entries.

The pipeline pauses after this step for visual review. If you edit `**Suggested Title:**` in the review file or want to regenerate one or more cover overlays, pressing `r` lists the covers created in this pass and lets you remove selected numbers/ranges, or `all`; then `yt_export.py --sync-titles` rewrites filenames/source lines/export log from the reviewed titles, and cover generation reruns. Existing covers that were not removed are skipped. Pressing Enter continues to the next stage.

### 3.4: Create MP4 Videos (Audio Mode only)
Combines thumbnails with MP3 audio files.

```bash
uv run python scripts/yt_video.py --lang ru|en [--folder <folder>] [--source-log <path>]
```

- **Input:** `output/thumbnails/<folder>/` and `output/audio/<folder>/`
- **Output:** `output/video/<folder>/`
- Normal `yt_run.sh` reruns scan approved entries and create only missing videos, while skipping anything already uploaded according to YouTube history.

### 3.4: Generate Cover Thumbnails (Video Mode + `--cover` only)
Composites a text overlay (title, teacher name, AI-generated highlights) onto the base thumbnail to create a YouTube cover image.

```bash
uv run python scripts/yt_cover_gen.py --lang ru|en [--folder <folder>] [--limit N] [--dry-run] [--list-fonts]
```

- **Input:** `output/thumbnails/<folder>/` (FLUX images from 3.2)
- **Output:** `output/covers/<folder>/`
- Only processes entries where `**Media:** video` is set in the review file.
- `--list-fonts` generates paginated font preview sheets (`temp/font_preview_<lang>_01.png`, …) and an index (`temp/font_list_<lang>.md`), then exits — useful for picking a font before the first run.
- Font and overlay parameters are configurable via `.env` (`COVER_FONT_PATH`, `COVER_RU_FONT_PATH`, `COVER_GRADIENT_HEIGHT_PCT`, etc.); all have sensible defaults and the script works with no `.env` entries.

The pipeline pauses after this step for visual review. Pressing `r` lists the files created in this run, asks for confirmation, deletes them, then reruns the generator. Pressing Enter continues to upload.

---

## Stage 4: Upload (YouTube & Google Drive)

### YouTube Upload
Uploads MP4s from `output/video/<folder>/`.

```bash
uv run python scripts/yt_upload.py --lang ru|en [--folder <folder>] [--dry-run] [--files-from-log <path>]
```

Videos are uploaded as **private** with a scheduled publish time (10 minutes from upload by default, or the date set in the review file). Once the publish time arrives, YouTube makes the video public and notifies subscribers.

Playlist membership comes only from `**Selected Playlist:**` in the review file. Before upload, the script fetches existing channel playlists and exact-matches selected titles after trimming whitespace. If a selected playlist is missing, the script prints a warning, uploads the video anyway, and adds it only to playlists that exist. It never creates playlists automatically.

Upload history in `output/youtube_history.json` is an extra safety guard: stages skip videos already marked `status: uploaded` when they can match the final MP4 filename exactly. Pass `--force` to rerun despite that history.

Normal `yt_run.sh` reruns scan the selected video folder and upload pending files that are approved in the review file and absent from YouTube upload history. Dry-runs still use `--files-from-log` so stub traces do not fall back to backlog scanning.

After each successful video upload, if a matching cover image exists at `output/covers/<folder>/<stem>.jpg`, it is automatically set as the YouTube thumbnail via the `thumbnails().set()` API.

### Google Drive Upload
Uploads MP4s and MP3s from their respective output directories.

```bash
uv run python scripts/gdrive_upload.py --lang ru|en [--folder <folder>] [--dry-run] [--files-from-log <path>]
```

Drive creates top-level `video/` and `audio/` folders under the configured language root. Video files always go under `video/`; audio files always go under `audio/`. `**Selected Playlist:**` is the only field that can add a subfolder inside those base folders. If one playlist is selected, that playlist name is used as the subfolder under both `video/` and `audio/`. If multiple playlists are selected, Drive asks which single subfolder to use. If `Selected Playlist` is blank, no extra subfolder is used.

Normal `yt_run.sh --gdrive` reruns scan pending approved media and skip files already marked uploaded in Drive history. Dry-runs still use `--files-from-log` so stub traces do not fall back to backlog scanning.
