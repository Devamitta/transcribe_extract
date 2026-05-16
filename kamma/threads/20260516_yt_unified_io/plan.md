# Plan: Unified Input/Output Directory Restructure for YouTube Pipeline

## Architecture Decisions
- **No `output/youtube/`**: `output/video/<folder>/` is both the working video dir and
  upload-ready dir. Audio mode writes newly-created mp4s there; video mode writes
  metadata-embedded originals there. Upload always reads from `output/video/`.
- **`--video-mode` removed**: auto-detected in `yt_run.sh` by checking `output/video/$FOLDER`
  for `.mp4` files after ingest.
- **In-place metadata embed**: `yt_export.py` writes ffmpeg output to a `.tmp` file,
  then renames over the original. No separate export-copy directory.
- **Review file = lang, not folder**: `reviews/english_review.md` and
  `reviews/russian_review.md` are the only two review files, always. All scripts that
  read/write a review file must use `LANG_TO_FOLDER[args.lang]` to find it, not the
  processing folder name.
- **Unified ingest replaces two scripts**: `yt_ingest_unified.py` handles video
  extraction, non-mp3 conversion, and mp3 movement in one pass. Removes the
  video/audio branch from `yt_run.sh`.
- **`setup_folders.sh` updated**: removes old dirs from creation, adds new ones.

---

## Phase 1: New Unified Ingest Script

### Task 1.1 — Write `scripts/yt_ingest_unified.py` [x]

Create `scripts/yt_ingest_unified.py` from scratch.

→ verify:
```bash
uv run python scripts/yt_ingest_unified.py --help   # exits 0
uv run python -m pyright scripts/yt_ingest_unified.py   # 0 errors
uv run ruff check scripts/yt_ingest_unified.py   # clean
```

---

## Phase 2: Update `yt_run.sh`

### Task 2.1 — Rewrite arg parsing and folder logic [x]

### Task 2.2 — Replace pipeline body [x]

→ verify: `bash -n yt_run.sh` exits 0.

---

## Phase 3: Update Path Constants in Downstream Scripts

### Task 3.1 — `scripts/yt_export.py` [x]
→ verify: `uv run python -m pyright scripts/yt_export.py` 0 errors; `uv run ruff check --fix` clean.

### Task 3.2 — `scripts/yt_metadata.py` [x]
→ verify: `uv run python -m pyright scripts/yt_metadata.py` 0 errors; ruff clean.

### Task 3.3 — `scripts/yt_chapters.py` [x]
→ verify: `uv run python -m pyright scripts/yt_chapters.py` 0 errors; ruff clean.

### Task 3.4 — `scripts/yt_image_gen.py` [x]
→ verify: pyright 0 errors; ruff clean.

### Task 3.5 — `scripts/yt_video.py` [x]
→ verify: pyright 0 errors; ruff clean.

### Task 3.6 — `scripts/yt_upload.py` [x]
→ verify: pyright 0 errors; ruff clean.

### Task 3.7 — `scripts/gdrive_upload.py` [x]
→ verify: pyright 0 errors; ruff clean.

### Task 3.8 — `tools/uploader_common.py` [x]
→ verify: pyright 0 errors; ruff clean.

---

## Phase 4: Delete Old Scripts

### Task 4.1 — Remove superseded ingest scripts [x]
→ verify: `ls scripts/yt_ingest.py scripts/yt_audio_convert.py` → "No such file".

---

## Phase 5: Update `setup_folders.sh`

### Task 5.1 — Replace old dir list with new structure [x]
→ verify: run `bash -n setup_folders.sh` exits 0; read the file and confirm old dirs gone.

---

## Phase 6: Update Docs

### Task 6.1 — Rewrite `docs/pipeline-youtube.md` [x]
→ verify: `grep -n "_audio\|_youtube\|_thumbnails\|video-mode\|yt_ingest\.py\|yt_audio_convert" docs/pipeline-youtube.md` returns no matches.

---

## Phase 7: Final Quality Check

### Task 7.1 — ruff + pyright on all modified files [x]
→ verify: all three commands exit 0.
