#!/bin/bash
# Unified YouTube pipeline for English and Russian talks (audio or video input).
# Usage: ./yt_run.sh --lang ru|en [folder] [--video-mode] [--from-export] [--gdrive] [--dry-run] [--context CONTEXT]
#   --lang: required; ru or en
#   folder: optional; defaults to 'russian' (ru) or 'english' (en)
#   --video-mode: ingest from .mp4 instead of .mp3; exports metadata back into mp4 and uploads
#   --from-export: skip transcription/metadata steps (assume review already done)
#   --gdrive: also upload to Google Drive (default: YouTube only)
#   --dry-run: pass --dry-run to upload steps
#   --context: whisper context tag; defaults to 'russian' (ru) or 'dhamma' (en)
set -e

LANG=""
FOLDER=""
FROM_EXPORT=0
VIDEO_MODE=0
DRY_RUN=0
GDRIVE=0
CONTEXT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang)        LANG="$2";    shift 2 ;;
    --context)     CONTEXT="$2"; shift 2 ;;
    --from-export) FROM_EXPORT=1; shift ;;
    --video-mode)  VIDEO_MODE=1;  shift ;;
    --dry-run)     DRY_RUN=1;     shift ;;
    --gdrive)      GDRIVE=1;      shift ;;
    -*) shift ;;
    *) FOLDER="$1"; shift ;;
  esac
done

if [ -z "$LANG" ]; then
  echo "Usage: ./yt_run.sh --lang ru|en [folder] [--video-mode] [--from-export] [--gdrive] [--dry-run] [--context CONTEXT]"
  exit 1
fi

if [ -z "$FOLDER" ]; then
  [ "$LANG" = "ru" ] && FOLDER="russian" || FOLDER="english"
fi

if [ -z "$CONTEXT" ]; then
  [ "$LANG" = "ru" ] && CONTEXT="russian" || CONTEXT="dhamma"
fi

DRY_RUN_FLAG=""
[ "$DRY_RUN" -eq 1 ] && DRY_RUN_FLAG="--dry-run"

if [ "$FROM_EXPORT" -eq 0 ]; then
  if [ "$VIDEO_MODE" -eq 1 ]; then
    # 1. Ingest video files (extract audio for transcription)
    uv run python scripts/yt_ingest.py --folder "$FOLDER"
  else
    # 1. Convert non-MP3 audio to MP3 in-place
    uv run python scripts/yt_audio_convert.py --folder "$FOLDER"
  fi

  # 2. Transcribe MP3 files using MLX Whisper
  caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
    --input-dir "audio/$FOLDER" \
    --context "$CONTEXT" --chunk-seconds 20

  # 3. Generate metadata suggestions
  uv run python scripts/yt_metadata.py --lang "$LANG" --folder "$FOLDER"

  # 4. Generate AI chapter timestamps
  uv run python scripts/yt_chapters.py --lang "$LANG" --folder "$FOLDER"

  echo ""
  echo "----------------------------------------------------------------"
  echo "METADATA GENERATED."
  echo "Please open reviews/${FOLDER}_review.md"
  echo "1. Fill in the 'Recording Date' (DD-MM-YYYY) for approved talks."
  echo "2. Review and edit titles and descriptions."
  echo "3. Press Enter here when finished to continue with export."
  echo "----------------------------------------------------------------"
  read -r _
fi

if [ "$VIDEO_MODE" -eq 1 ]; then
  # 5. Embed metadata into source .mp4 and move to upload folder
  uv run python scripts/yt_export.py --folder "$FOLDER" --video-mode

  # 6. Upload to YouTube
  uv run python scripts/yt_upload.py --lang "$LANG" --folder "$FOLDER" \
    --input-dir "output/${FOLDER}_video_upload" $DRY_RUN_FLAG

  if [ "$GDRIVE" -eq 1 ]; then
    # 7. Upload to Google Drive
    uv run python scripts/gdrive_upload.py --lang "$LANG" --folder "$FOLDER" \
      --input-dir "output/${FOLDER}_video_upload" $DRY_RUN_FLAG
  fi
else
  # 5. Rename files by date and export with metadata
  uv run python scripts/yt_export.py --folder "$FOLDER"

  # 6. Generate thumbnail images
  uv run python scripts/yt_image_gen.py --lang "$LANG" --folder "$FOLDER"

  echo ""
  echo "----------------------------------------------------------------"
  echo "IMAGES GENERATED."
  echo "Please review the thumbnails in output/${FOLDER}_thumbnails/"
  echo "Press Enter when finished to continue with video creation."
  echo "----------------------------------------------------------------"
  read -r _

  # 7. Create MP4 videos
  uv run python scripts/yt_video.py --folder "$FOLDER"

  # 8. Upload to YouTube
  uv run python scripts/yt_upload.py --lang "$LANG" --folder "$FOLDER" $DRY_RUN_FLAG

  if [ "$GDRIVE" -eq 1 ]; then
    # 9. Upload to Google Drive
    uv run python scripts/gdrive_upload.py --lang "$LANG" --folder "$FOLDER" $DRY_RUN_FLAG
  fi
fi

echo ""
echo "PIPELINE COMPLETE."
