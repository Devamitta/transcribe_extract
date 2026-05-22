#!/bin/bash
# Unified YouTube pipeline for English and Russian talks (audio or video input).
# Usage: ./yt_run.sh [--lang ru|en] [--folder folder] [--from-export] [--video-mode] [--gdrive] [--dry-run] [--context CONTEXT]
#   --lang: optional; ru or en (defaults to en for review file selection)
#   --folder: optional; specific folder in input/ to scan
#   --from-export: skip transcription/metadata steps (assume review already done)
#   --video-mode: treat source files as raw video (skip thumbnail+video generation); only needed with --from-export
#   --gdrive: also upload to Google Drive (default: YouTube only)
#   --dry-run: pass --dry-run to upload steps
#   --context: whisper context tag; defaults to 'russian' (ru) or 'dhamma' (en)
set -e

LANG=""
FOLDER=""
NAME=""
FROM_EXPORT=0
DRY_RUN=0
GDRIVE=0
CONTEXT=""
VIDEO_MODE_OVERRIDE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang)        LANG="$2";    shift 2 ;;
    --folder)      FOLDER="$2";  shift 2 ;;
    --name)        NAME="$2";    shift 2 ;;
    --context)     CONTEXT="$2"; shift 2 ;;
    --from-export) FROM_EXPORT=1; shift ;;
    --video-mode)  VIDEO_MODE_OVERRIDE=1; shift ;;
    --dry-run)     DRY_RUN=1;     shift ;;
    --gdrive)      GDRIVE=1;      shift ;;
    -*) shift ;;
    *) FOLDER="$1"; shift ;;
  esac
done

# Resolve EFFECTIVE_FOLDER for paths
if [ -n "$FOLDER" ]; then
  EFFECTIVE_FOLDER="$FOLDER"
elif [ -n "$LANG" ]; then
  [ "$LANG" = "ru" ] && EFFECTIVE_FOLDER="russian" || EFFECTIVE_FOLDER="english"
else
  EFFECTIVE_FOLDER=""   # scan input/ root; preserve subfolder structure
fi

# Default LANG to en for review file only
[ -z "$LANG" ] && LANG="en"

# Default CONTEXT
if [ -z "$CONTEXT" ]; then
  [ "$LANG" = "ru" ] && CONTEXT="russian" || CONTEXT="dhamma"
fi

DRY_RUN_FLAG=""
[ "$DRY_RUN" -eq 1 ] && DRY_RUN_FLAG="--dry-run"

if [ "$FROM_EXPORT" -eq 0 ]; then
  # 1. Detect video mode from input/ BEFORE ingest moves files to output/
  VIDEO_MODE=0
  if [ -n "$EFFECTIVE_FOLDER" ]; then
    INPUT_SCAN_DIR="input/$EFFECTIVE_FOLDER"
  else
    INPUT_SCAN_DIR="input"
  fi
  if [ -d "$INPUT_SCAN_DIR" ] && [ -n "$(find "$INPUT_SCAN_DIR" -name "*.mp4" -print -quit)" ]; then
    VIDEO_MODE=1
  fi

  # 2. Unified ingest
  echo "→ Starting: yt_ingest_unified.py"
  INGEST_ARGS=""
  [ -n "$FOLDER" ] && INGEST_ARGS="--folder $FOLDER"
  [ -z "$FOLDER" ] && [ -n "$LANG" ] && INGEST_ARGS="--lang $LANG"
  uv run python scripts/yt_ingest_unified.py $INGEST_ARGS

  # 2b. Dedup check — resolve duplicate dates before transcription
  echo "→ Starting: yt_review_dedup.py"
  uv run python scripts/yt_review_dedup.py --lang "$LANG"

  # 3. Transcribe
  echo "→ Starting: transcribe.py (caffeinate, background priority)"
  TRANSCRIBE_ARGS="--lang $LANG"
  [ -n "$FOLDER" ] && TRANSCRIBE_ARGS="$TRANSCRIBE_ARGS --folder $FOLDER"
  caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
    $TRANSCRIBE_ARGS \
    --context "$CONTEXT" --chunk-seconds 20

  # 4. Metadata
  echo "→ Starting: yt_metadata.py"
  uv run python scripts/yt_metadata.py --lang "$LANG" \
    ${FOLDER:+--folder "$FOLDER"} \
    ${NAME:+--name "$NAME"}

  # 5. Chapters
  echo "→ Starting: yt_chapters.py"
  uv run python scripts/yt_chapters.py --lang "$LANG" \
    ${FOLDER:+--folder "$FOLDER"}

  LANG_FOLDER="english"
  [ "$LANG" = "ru" ] && LANG_FOLDER="russian"

  echo ""
  echo "----------------------------------------------------------------"
  echo "METADATA GENERATED."
  echo "Please open reviews/${LANG_FOLDER}_review.md"
  echo "Fill Recording Date, review titles/descriptions, then press Enter."
  echo "----------------------------------------------------------------"
  read -r _

  # 5b. Dedup check — resolve any duplicates introduced after user review
  echo "→ Starting: yt_review_dedup.py (post-review check)"
  uv run python scripts/yt_review_dedup.py --lang "$LANG"
fi

# For FROM_EXPORT, input/ is already empty; default to audio mode unless --video-mode passed
if [ "$FROM_EXPORT" -eq 1 ]; then
  VIDEO_MODE=$VIDEO_MODE_OVERRIDE
fi

# 6. Export (rename + embed metadata in-place)
echo "→ Starting: yt_export.py"
EXPORT_FLAGS=""
[ "$VIDEO_MODE" -eq 1 ] && EXPORT_FLAGS="--video-mode"
uv run python scripts/yt_export.py --lang "$LANG" \
  ${FOLDER:+--folder "$FOLDER"} \
  ${NAME:+--name "$NAME"} \
  $EXPORT_FLAGS $DRY_RUN_FLAG

if [ "$VIDEO_MODE" -eq 0 ]; then
  # 7. Thumbnails
  while true; do
    echo "→ Starting: yt_image_gen.py"
    uv run python scripts/yt_image_gen.py --lang "$LANG" \
      ${FOLDER:+--folder "$FOLDER"}

    echo ""
    echo "----------------------------------------------------------------"
    echo "IMAGES GENERATED."
    THUMB_DIR="output/thumbnails"
    [ -n "$EFFECTIVE_FOLDER" ] && THUMB_DIR="output/thumbnails/$EFFECTIVE_FOLDER"
    echo "Review thumbnails in $THUMB_DIR"
    echo "Press Enter to continue, or 'r' to re-run image generation."
    echo "----------------------------------------------------------------"
    read -r user_input
    if [ "$user_input" != "r" ] && [ "$user_input" != "R" ]; then
      break
    fi
  done

  # 8. Create MP4 videos → output/video/
  echo "→ Starting: yt_video.py"
  uv run python scripts/yt_video.py --lang "$LANG" \
    ${FOLDER:+--folder "$FOLDER"}
fi

# 9. Upload to YouTube (from output/video/)
echo "→ Starting: yt_upload.py"
uv run python scripts/yt_upload.py --lang "$LANG" \
  ${FOLDER:+--folder "$FOLDER"} $DRY_RUN_FLAG

if [ "$GDRIVE" -eq 1 ]; then
  # 10. Upload to Google Drive
  echo "→ Starting: gdrive_upload.py"
  uv run python scripts/gdrive_upload.py --lang "$LANG" \
    ${FOLDER:+--folder "$FOLDER"} $DRY_RUN_FLAG
fi

echo ""
echo "PIPELINE COMPLETE."
