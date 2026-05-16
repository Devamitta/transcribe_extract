# Spec: Unified Input/Output Directory Restructure for YouTube Pipeline

## Overview
Consolidate the YouTube pipeline around a single `input/` staging folder and a clean
`output/<type>/<folder>/` directory structure. Users drop any file (video or audio,
any format) into `input/` or `input/<folder>/`. A new unified ingest script auto-detects
file type, converts everything to MP3, and moves originals out. All downstream scripts
read/write under `output/`. The `--video-mode` flag is removed; mode is auto-detected
from whether `output/video/<folder>/` contains files after ingest.

The old `audio/` and `video/` root input dirs are removed. Old flat output dirs
(`output/english_audio/`, `output/russian_thumbnails/`, etc.) are replaced with
namespaced ones (`output/audio/english/`, `output/thumbnails/russian/`, etc.).
`output/youtube/` does not exist — `output/video/` serves as both working video dir
and upload-ready dir.

Default `--lang` changes from required to optional (defaults to `en` for review file
selection only; input folder defaults to `input/` root when neither `--lang` nor
`--folder` is given).

---

## Directory Contract

| Role | Old Path | New Path |
|------|----------|----------|
| User input (staging) | `audio/<folder>/` or `video/<folder>/` | `input/` or `input/<folder>/` |
| Working MP3s | `audio/<folder>/` | `output/audio/<folder>/` |
| Working/upload video | `video/<folder>/` + `output/<folder>_video_upload/` | `output/video/<folder>/` |
| Exported audio (upload-ready) | `output/<folder>_audio/` | `output/audio/<folder>/` (in-place metadata) |
| Thumbnails | `output/<folder>_thumbnails/` | `output/thumbnails/<folder>/` |
| YouTube MP4s | `output/<folder>_youtube/` | `output/video/<folder>/` (same as video) |
| Transcripts | `output/transcribed/<folder>/` | unchanged |
| Reviews | `reviews/<folder>_review.md` | `reviews/english_review.md` or `reviews/russian_review.md` (always lang-based, never folder-based) |

---

## Folder Resolution Logic

| Invocation | Scans | Output dirs | Review file |
|---|---|---|---|
| `./yt_run.sh` (no args) | `input/` root (subfolders preserved) | `output/audio/`, `output/video/` | `reviews/english_review.md` |
| `./yt_run.sh --lang en` | `input/english/` | `output/audio/english/` etc. | `reviews/english_review.md` |
| `./yt_run.sh --lang ru` | `input/russian/` | `output/audio/russian/` etc. | `reviews/russian_review.md` |
| `./yt_run.sh --lang en --folder interview` | `input/interview/` | `output/audio/interview/` etc. | `reviews/english_review.md` |
| `./yt_run.sh --lang ru --folder sangha` | `input/sangha/` | `output/audio/sangha/` etc. | `reviews/russian_review.md` |

Review file is always determined by `--lang` (defaulting to `en`), never by `--folder`.

---

## What Changes

### NEW: `scripts/yt_ingest_unified.py`
Replaces `yt_ingest.py` + `yt_audio_convert.py`. Scans `input/` or `input/<folder>/`.

- **Video** (`.mp4`, `.mkv`, `.mov`, case-insensitive): extract MP3 → `output/audio/<folder>/`, move original → `output/video/<folder>/`, print warning
- **Non-MP3 audio** (`.wav`, `.m4a`, `.aiff`, `.flac`, `.ogg`, `.opus`, `.wma`): convert to MP3 → `output/audio/<folder>/`, remove from `input/`
- **MP3**: move to `output/audio/<folder>/`
- Idempotent: skip if target already exists. Nothing in `input/` modified in-place.
- No-folder mode: scans all immediate subfolders of `input/`; each subfolder name becomes the folder in output paths

### DELETED
- `scripts/yt_ingest.py`
- `scripts/yt_audio_convert.py`

### `yt_run.sh`
- `--lang` optional; defaults to `en` for review file selection only
- `--video-mode` flag removed entirely
- Step 1: always `yt_ingest_unified.py`
- Step 2: auto-detect video mode by checking `output/video/$EFFECTIVE_FOLDER/*.mp4`
- Transcription `--input-dir` → `output/audio/$EFFECTIVE_FOLDER`
- All downstream path args updated

### `scripts/yt_export.py`
- `audio_base = Path("audio")` → `Path("output/audio")`
- `video_base = Path("video")` → `Path("output/video")`
- Output dirs: in-place metadata embed (ffmpeg → `.tmp` file, rename over original)
- Review file lookup: use `LANG_TO_FOLDER[args.lang]`, not `folder_name`

### `scripts/yt_metadata.py`
- Review file: use `LANG_TO_FOLDER[args.lang]` to name the review file, not `folder_name`

### `scripts/yt_chapters.py`
- Same as `yt_metadata.py`

### `scripts/yt_image_gen.py`
- `output/<folder>_thumbnails` → `output/thumbnails/<folder>`

### `scripts/yt_video.py`
- audio: `output/<folder>_audio` → `output/audio/<folder>`
- thumbs: `output/<folder>_thumbnails` → `output/thumbnails/<folder>`
- output: `output/<folder>_youtube` → `output/video/<folder>`
- Review file lookup: use lang, not folder_name

### `scripts/yt_upload.py`
- `output/<folder>_youtube` → `output/video/<folder>`
- Review file lookup: use lang, not folder_name

### `scripts/gdrive_upload.py`
- `output/<folder>_youtube` → `output/video/<folder>`
- `output/<folder>_audio` → `output/audio/<folder>`
- Review file lookup: use lang, not folder_name

### `tools/uploader_common.py`
- `find_audio_for_mp4` default: `Path("audio/russian")` → `Path("output/audio")`

### `setup_folders.sh`
- Remove: `audio/`, `video/`, `output/english_audio`, `output/russian_audio`,
  `output/english_thumbnails`, `output/russian_thumbnails`, `output/english_youtube`,
  `output/russian_youtube`
- Add: `input/`, `output/audio/`, `output/video/`, `output/thumbnails/`

### `docs/pipeline-youtube.md`
- All path references updated to new structure; `--video-mode` removed from docs

---

## What Does NOT Change
- `transcribe.py` — already parameterized via `--input-dir`
- Review file naming convention (english/russian) — unchanged
- All pipeline logic — only path constants and review file lookup change

## Assumptions
- Existing files in old `audio/` / `video/` dirs are NOT auto-migrated
- In-place metadata embed: ffmpeg writes to `.tmp`, renames over original
- Auto-detect video mode in `yt_run.sh`: `ls output/video/$FOLDER/*.mp4 2>/dev/null | grep -q .`
- `input/` directory created with helpful message if absent on first run
- No-folder scan preserves one level of subfolder only (files at `input/` root go to `output/audio/` flat)

## How We'll Know It's Done
- `./yt_run.sh` (no args) scans `input/`, preserves subfolder structure in output
- `./yt_run.sh --lang ru` scans `input/russian/`, review = `reviews/russian_review.md`
- `./yt_run.sh --lang en --folder interview` scans `input/interview/`, review = `reviews/english_review.md`
- Dropping `.mp4` into `input/english/` → mp3 in `output/audio/english/`, mp4 in `output/video/english/`
- Dropping `.wav` → mp3 in `output/audio/<folder>/`, wav removed from input/
- All old flat output dirs (`english_audio`, etc.) gone
- `ruff` + `pyright` pass on all modified scripts

## What's Not Included
- Auto-migration of old `audio/` / `video/` dirs
- Reviews git branch sync (separate thread: `20260516_reviews_branch_sync`)
- Recursive subfolder nesting inside `input/<folder>/`
