#!/bin/bash
# Unified YouTube pipeline for English and Russian talks (audio or video input).
# Usage: ./yt_run.sh [--lang ru|en] [--folder folder] [--name NAME] [--from-export] [--video-mode] [--cover] [--gdrive] [--dry-run] [--context CONTEXT]
#   --lang: optional; ru or en (defaults to en for review file selection)
#   --folder: optional; specific folder in input/ to scan
#   --name: optional; override speaker/artist name in titles and embedded metadata
#   --from-export: skip transcription/metadata steps (assume review already done)
#   --video-mode: treat source files as raw video (skip thumbnail+video generation); only needed with --from-export
#   --cover: (video mode only) generate base + cover thumbnails and set them on YouTube after upload
#   --gdrive: also upload to Google Drive (default: YouTube only)
#   --dry-run [file]: trace the full pipeline without real processing; optional stub e.g. russian/test.mp4
#   --context: whisper context tag; defaults to 'russian' (ru) or 'dhamma' (en)
set -e

LANG=""
FOLDER=""
NAME=""
FROM_EXPORT=0
DRY_RUN=0
DRY_RUN_STUB=""
GDRIVE=0
CONTEXT=""
VIDEO_MODE_OVERRIDE=0
COVER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang)        LANG="$2";    shift 2 ;;
    --folder)      FOLDER="$2";  shift 2 ;;
    --name)        NAME="$2";    shift 2 ;;
    --context)     CONTEXT="$2"; shift 2 ;;
    --from-export) FROM_EXPORT=1; shift ;;
    --video-mode)  VIDEO_MODE_OVERRIDE=1; shift ;;
    --cover)       COVER=1;       shift ;;
    --dry-run)
      DRY_RUN=1; shift
      if [[ $# -gt 0 ]] && [[ "$1" != --* ]]; then
        DRY_RUN_STUB="$1"; shift
      fi
      ;;
    --gdrive)      GDRIVE=1;      shift ;;
    --limit)       LIMIT="$2";   shift 2 ;;
    -*) shift ;;
    *)
      if [ "$DRY_RUN" -eq 1 ] && [ -z "$DRY_RUN_STUB" ]; then
        DRY_RUN_STUB="$1"
      else
        FOLDER="$1"
      fi
      shift
      ;;
  esac
done

# Save user-specified values before defaulting
USER_LANG="$LANG"
USER_FOLDER="$FOLDER"
ALBUM_MODE=0

# Resolve EFFECTIVE_FOLDER:
#   --folder  → use it directly
#   --lang    → derive from lang (russian/english)
#   dry-run stub → derive from stub path (subdirectory = album mode)
#   none      → auto-detect from input/ (root files = root mode; subfolder = album mode)
if [ -n "$USER_FOLDER" ]; then
  EFFECTIVE_FOLDER="$USER_FOLDER"
elif [ -n "$USER_LANG" ]; then
  [ "$USER_LANG" = "ru" ] && EFFECTIVE_FOLDER="russian" || EFFECTIVE_FOLDER="english"
elif [ "$DRY_RUN" -eq 1 ] && [ -n "$DRY_RUN_STUB" ]; then
  _stub_subdir=$(dirname "$DRY_RUN_STUB")
  if [ "$_stub_subdir" = "." ]; then
    EFFECTIVE_FOLDER=""
  else
    EFFECTIVE_FOLDER="$_stub_subdir"
    ALBUM_MODE=1
  fi
else
  # Auto-detect: root-level media files → root mode; first subfolder with media → album mode
  EFFECTIVE_FOLDER=""
  if ! find "input" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.mp3" -o -name "*.wav" \
        -o -name "*.m4a" -o -name "*.aiff" -o -name "*.flac" -o -name "*.ogg" \
        -o -name "*.opus" -o -name "*.wma" \) -print -quit 2>/dev/null | grep -q .; then
    for subdir in input/*/; do
      [ -d "$subdir" ] || continue
      if find "$subdir" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.mp3" \) \
            -print -quit 2>/dev/null | grep -q .; then
        EFFECTIVE_FOLDER=$(basename "$subdir")
        ALBUM_MODE=1
        break
      fi
    done
  fi
fi

# Default LANG (used for LLM prompts and review file naming)
[ -z "$LANG" ] && LANG="en"

# LANG_FOLDER drives review file names (reviews/english_review.md etc.) — always language-based
LANG_FOLDER="english"
[ "$LANG" = "ru" ] && LANG_FOLDER="russian"

# Default CONTEXT
if [ -z "$CONTEXT" ]; then
  [ "$LANG" = "ru" ] && CONTEXT="russian" || CONTEXT="dhamma"
fi

DRY_RUN_FLAG=""
DRY_RUN_CLEANUP="temp/.dry_run_cleanup"

if [ "$DRY_RUN" -eq 1 ]; then
  DRY_RUN_FLAG="--dry-run"
  mkdir -p temp
  rm -f "temp/.dry_run_active"
  > "$DRY_RUN_CLEANUP"
  touch "temp/.dry_run_active"
  if [ -n "$DRY_RUN_STUB" ]; then
    STUB_SUBDIR=$(dirname "$DRY_RUN_STUB")
    STUB_FILE=$(basename "$DRY_RUN_STUB")
    if [ "$STUB_SUBDIR" = "." ]; then
      if [ -n "$EFFECTIVE_FOLDER" ]; then
        mkdir -p "input/$EFFECTIVE_FOLDER"
        STUB_PATH="input/$EFFECTIVE_FOLDER/$STUB_FILE"
      else
        STUB_PATH="input/$STUB_FILE"
      fi
    else
      mkdir -p "input/$STUB_SUBDIR"
      STUB_PATH="input/$DRY_RUN_STUB"
    fi
    touch "$STUB_PATH"
    echo "$STUB_PATH" >> "$DRY_RUN_CLEANUP"
    echo "→ [DRY RUN] Stub created: $STUB_PATH"
  fi
fi

if [ "$FROM_EXPORT" -eq 0 ]; then
  # 1. Detect video mode from input/ BEFORE ingest moves files to output/
  VIDEO_MODE=0
  INPUT_SCAN_DIR="input${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
  if [ -d "$INPUT_SCAN_DIR" ] && \
      [ -n "$(find "$INPUT_SCAN_DIR" -maxdepth 1 -name "*.mp4" -print -quit 2>/dev/null)" ]; then
    VIDEO_MODE=1
  fi
  EXPORT_FLAGS=""
  [ "$VIDEO_MODE" -eq 1 ] && EXPORT_FLAGS="--video-mode"

  # 2. Unified ingest
  echo "→ Starting: yt_ingest_unified.py"
  INGEST_ARGS=""
  [ -n "$EFFECTIVE_FOLDER" ] && INGEST_ARGS="--folder $EFFECTIVE_FOLDER"
  [ -z "$EFFECTIVE_FOLDER" ] && [ -n "$USER_LANG" ] && INGEST_ARGS="--lang $USER_LANG"
  uv run python scripts/yt_ingest_unified.py $INGEST_ARGS $DRY_RUN_FLAG

  # 2b. Dedup check — resolve duplicate dates before transcription
  echo "→ Starting: yt_review_dedup.py"
  uv run python scripts/yt_review_dedup.py --lang "$LANG" $DRY_RUN_FLAG

  # 3. Transcribe
  echo "→ Starting: transcribe.py (caffeinate, background priority)"
  TRANSCRIBE_LOG=$(mktemp)
  caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
    --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" \
    --context "$CONTEXT" --chunk-seconds 20 --created-log "$TRANSCRIBE_LOG" $DRY_RUN_FLAG

  # 3b. Verify transcription duration (only files created in this run)
  echo "→ Starting: verify_duration.py"
  AUDIO_SUBDIR="output/audio${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
  TRANSCRIPT_SUBDIR="output/transcribed${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
  if ! uv run python scripts/verify_duration.py \
    --audio-dir "$AUDIO_SUBDIR" \
    --transcript-dir "$TRANSCRIPT_SUBDIR" \
    --created-log "$TRANSCRIBE_LOG" $DRY_RUN_FLAG; then
    echo "Warning: Some transcripts may be truncated. Check the report above."
  fi
  rm -f "$TRANSCRIBE_LOG"

  # 4. Metadata
  echo "→ Starting: yt_metadata.py"
  METADATA_LANG_FLAG=""
  [ -n "$USER_LANG" ] && METADATA_LANG_FLAG="--lang $USER_LANG"
  uv run python scripts/yt_metadata.py $METADATA_LANG_FLAG \
    --folder "$EFFECTIVE_FOLDER" \
    ${NAME:+--name "$NAME"} \
    $EXPORT_FLAGS $DRY_RUN_FLAG

  echo ""
  echo "----------------------------------------------------------------"
  echo "OPTIONAL: Pre-fill chapter names for AI timing."
  echo "Open reviews/${LANG_FOLDER}_review.md"
  echo "After **Suggested Tags:** add a **Chapters:** block with one"
  echo "chapter name per line (no timestamps — AI will find them):"
  echo ""
  echo "  **Chapters:**"
  echo "  Introduction"
  echo "  The Nature of Mind"
  echo "  Questions and Answers"
  echo ""
  echo "Leave it out to let AI generate chapters automatically."
  echo "Press Enter when ready."
  echo "----------------------------------------------------------------"
  [ "$DRY_RUN" -eq 1 ] || read -r _

  # 5. Chapters
  echo "→ Starting: yt_chapters.py"
  uv run python scripts/yt_chapters.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" $DRY_RUN_FLAG

  echo ""
  echo "----------------------------------------------------------------"
  echo "METADATA GENERATED."
  echo "Please open reviews/${LANG_FOLDER}_review.md"
  echo "Fill Recording Date, review titles/descriptions, then press Enter."
  echo "----------------------------------------------------------------"
  [ "$DRY_RUN" -eq 1 ] || read -r _

  # 5b. Dedup check — resolve any duplicates introduced after user review
  echo "→ Starting: yt_review_dedup.py (post-review check)"
  uv run python scripts/yt_review_dedup.py --lang "$LANG" $DRY_RUN_FLAG
fi

# For FROM_EXPORT, input/ is already empty; default to audio mode unless --video-mode passed
if [ "$FROM_EXPORT" -eq 1 ]; then
  VIDEO_MODE=$VIDEO_MODE_OVERRIDE
fi

# Shared flag passed to any script that needs to know video vs audio mode
EXPORT_FLAGS=""
[ "$VIDEO_MODE" -eq 1 ] && EXPORT_FLAGS="--video-mode"

# Show files created in this run (from log) and offer to delete them before re-running.
confirm_and_remove_log() {
  local log="$1"
  if [ ! -s "$log" ]; then
    echo "No files were created in this run — nothing to remove."
    return
  fi
  echo "The following files will be removed before re-running:"
  while IFS= read -r f; do
    echo "  $f"
  done < "$log"
  printf "Confirm removal? [y/N] "
  read -r confirm_del
  if [ "$confirm_del" = "y" ] || [ "$confirm_del" = "Y" ]; then
    local count=0
    while IFS= read -r f; do
      [ -f "$f" ] && rm "$f" && count=$((count + 1))
    done < "$log"
    echo "Removed $count file(s)."
  else
    echo "Skipped removal — re-running without clearing existing files."
  fi
}

# 6. Export (rename + embed metadata in-place)
echo "→ Starting: yt_export.py"
EXPORT_LOG=$(mktemp)
uv run python scripts/yt_export.py --lang "$LANG" \
  --folder "$EFFECTIVE_FOLDER" \
  ${NAME:+--name "$NAME"} \
  --created-log "$EXPORT_LOG" \
  $EXPORT_FLAGS $DRY_RUN_FLAG

# 7. Thumbnails — audio mode always; video mode only with --cover
if [ "$VIDEO_MODE" -eq 0 ] || [ "$COVER" -eq 1 ]; then
  while true; do
    THUMB_LOG=$(mktemp)
    echo "→ Starting: yt_image_gen.py"
    uv run python scripts/yt_image_gen.py --lang "$LANG" \
      --folder "$EFFECTIVE_FOLDER" --created-log "$THUMB_LOG" $DRY_RUN_FLAG

    echo ""
    echo "----------------------------------------------------------------"
    echo "IMAGES GENERATED."
    THUMB_DIR="output/thumbnails${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
    echo "Review thumbnails in $THUMB_DIR"
    echo "Press Enter to continue, or 'r' to re-run image generation."
    echo "----------------------------------------------------------------"
    if [ "$DRY_RUN" -eq 1 ]; then rm -f "$THUMB_LOG"; break; fi
    read -r user_input
    if [ "$user_input" != "r" ] && [ "$user_input" != "R" ]; then
      rm -f "$THUMB_LOG"
      break
    fi
    confirm_and_remove_log "$THUMB_LOG"
    rm -f "$THUMB_LOG"
  done
fi

if [ "$VIDEO_MODE" -eq 0 ]; then
  # 8. Create MP4 videos → output/video/
  echo "→ Starting: yt_video.py"
  uv run python scripts/yt_video.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" $DRY_RUN_FLAG
fi

if [ "$VIDEO_MODE" -eq 1 ] && [ "$COVER" -eq 1 ]; then
  # 7b. Cover thumbnails (video mode + --cover only)
  while true; do
    COVER_LOG=$(mktemp)
    echo "→ Starting: yt_cover_gen.py"
    uv run python scripts/yt_cover_gen.py --lang "$LANG" \
      --folder "$EFFECTIVE_FOLDER" --created-log "$COVER_LOG" $DRY_RUN_FLAG

    echo ""
    echo "----------------------------------------------------------------"
    echo "COVERS GENERATED."
    COVER_DIR="output/covers${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
    echo "Review covers in $COVER_DIR"
    echo "Press Enter to continue, or 'r' to re-run cover generation."
    echo "----------------------------------------------------------------"
    if [ "$DRY_RUN" -eq 1 ]; then rm -f "$COVER_LOG"; break; fi
    read -r user_input
    if [ "$user_input" != "r" ] && [ "$user_input" != "R" ]; then
      rm -f "$COVER_LOG"
      break
    fi
    confirm_and_remove_log "$COVER_LOG"
    rm -f "$COVER_LOG"
  done
fi

# 9. Upload to YouTube (from output/video/)
echo "→ Starting: yt_upload.py"
UPLOAD_FILES_FLAG=""
[ "$DRY_RUN" -ne 1 ] && [ -s "$EXPORT_LOG" ] && UPLOAD_FILES_FLAG="--files-from-log $EXPORT_LOG"
if [ "$ALBUM_MODE" -eq 1 ]; then
  # Album mode: scan output/video/ root so subdirectory names become playlist names
  uv run python scripts/yt_upload.py --lang "$LANG" \
    --input-dir "output/video/" $UPLOAD_FILES_FLAG $DRY_RUN_FLAG
else
  uv run python scripts/yt_upload.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" $UPLOAD_FILES_FLAG $DRY_RUN_FLAG
fi
rm -f "$EXPORT_LOG"

if [ "$GDRIVE" -eq 1 ]; then
  # 10. Upload to Google Drive
  echo "→ Starting: gdrive_upload.py"
  uv run python scripts/gdrive_upload.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" $DRY_RUN_FLAG
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo ""
  echo "→ [DRY RUN] Cleaning up stubs..."
  if [ -f "$DRY_RUN_CLEANUP" ]; then
    while IFS= read -r stub_path; do
      [ -f "$stub_path" ] && rm "$stub_path"
    done < "$DRY_RUN_CLEANUP"
    rm -f "$DRY_RUN_CLEANUP"
  fi
  uv run python scripts/yt_dry_run_cleanup.py --lang "$LANG"
  rm -f "temp/.dry_run_active"
  echo "→ [DRY RUN] Cleanup complete."
fi

echo ""
echo "PIPELINE COMPLETE."
