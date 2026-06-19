#!/bin/bash
# Unified YouTube pipeline for English and Russian talks (audio or video input).
# Usage: ./yt_run.sh [--lang ru|en] [--folder folder] [--name NAME] [--from-export] [--video-mode] [--cover] [--gdrive] [--dry-run] [--force] [--context CONTEXT] [--limit N]
#   --lang: optional; ru or en (defaults to en for review file selection)
#   --folder: optional; specific folder in input/ to scan
#   --name: optional; override speaker/artist name; omitted defaults are language-derived
#   --from-export: deprecated compatibility flag; reruns are resumable by default
#   --video-mode: treat source/output files as raw video (skip audio thumbnail+video generation)
#   --cover: generate AI thumbnails/covers in video mode (yt_image_gen + yt_cover_gen); input images always copied to thumbnails/ and covers/ regardless
#   --gdrive: also upload to Google Drive (default: YouTube only)
#   --dry-run [file]: trace the full pipeline without real processing; optional stub e.g. russian/test.mp4
#   --force: bypass YouTube upload-history safety skips in supported stages
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
LIMIT=0
FORCE=0

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
    --force)       FORCE=1;       shift ;;
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
SUBFOLDER_MODE=0

# Resolve EFFECTIVE_FOLDER:
#   --folder  → use it directly
#   --lang    → derive from lang (russian/english)
#   dry-run stub → derive from stub path (subdirectory = subfolder mode)
#   none      → auto-detect from input/ (root files = root mode; subfolder = subfolder mode)
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
    SUBFOLDER_MODE=1
  fi
else
  # Auto-detect: root-level media files → root mode; first subfolder with media → subfolder mode
  EFFECTIVE_FOLDER=""
  if ! find "input" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.mp3" -o -name "*.wav" \
        -o -name "*.m4a" -o -name "*.aiff" -o -name "*.flac" -o -name "*.ogg" \
        -o -name "*.opus" -o -name "*.wma" \) -print -quit 2>/dev/null | grep -q .; then
    for subdir in input/*/; do
      [ -d "$subdir" ] || continue
      if find "$subdir" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.mp3" \) \
            -print -quit 2>/dev/null | grep -q .; then
        EFFECTIVE_FOLDER=$(basename "$subdir")
        SUBFOLDER_MODE=1
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
LIMIT_FLAG=""
[ "$LIMIT" -gt 0 ] && LIMIT_FLAG="--limit $LIMIT"
FORCE_FLAG=""
[ "$FORCE" -eq 1 ] && FORCE_FLAG="--force"

if [ "$FROM_EXPORT" -eq 1 ]; then
  echo "→ --from-export is deprecated; running the resumable pipeline from the beginning."
  FROM_EXPORT=0
fi

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
  VIDEO_MODE=$VIDEO_MODE_OVERRIDE
  EXPORT_FLAGS=""
  [ "$VIDEO_MODE" -eq 1 ] && EXPORT_FLAGS="--video-mode"

  INPUT_SCAN_DIR="input${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
  if [ "$DRY_RUN" -eq 0 ]; then
    # Guard 1: video in input but --video-mode not set
    if [ "$VIDEO_MODE_OVERRIDE" -eq 0 ]; then
      if find "$INPUT_SCAN_DIR" -maxdepth 1 \
        \( -name "*.mp4" -o -name "*.mpeg" -o -name "*.mpg" \) \
        -print -quit 2>/dev/null | grep -q .; then
        printf "⚠  Video files found in %s but --video-mode not set. Run in audio mode? [Y/n] " "$INPUT_SCAN_DIR"
        read -r _mm
        [ "$_mm" = "n" ] || [ "$_mm" = "N" ] && {
          echo "Aborted."
          exit 1
        }
      fi
    fi
    # Guard 2: --video-mode set but no video in input
    if [ "$VIDEO_MODE_OVERRIDE" -eq 1 ]; then
      OUTPUT_VIDEO_DIR="output/video${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
      if ! find "$INPUT_SCAN_DIR" -maxdepth 1 \
        \( -name "*.mp4" -o -name "*.mpeg" -o -name "*.mpg" \) \
        -print -quit 2>/dev/null | grep -q . \
        && ! find "$OUTPUT_VIDEO_DIR" -maxdepth 1 -name "*.mp4" \
        -print -quit 2>/dev/null | grep -q .; then
        printf "⚠  --video-mode set but no video files found in %s or %s. Continue? [y/N] " "$INPUT_SCAN_DIR" "$OUTPUT_VIDEO_DIR"
        read -r _mm
        [ "$_mm" != "y" ] && [ "$_mm" != "Y" ] && {
          echo "Aborted."
          exit 1
        }
      fi
    fi
  fi

  if [ "$DRY_RUN" -eq 0 ]; then
    printf "⚠ Source files in input/ will be converted (→ MP4/MP3/JPG), processed, and removed from the input folder. Press Enter to continue, or n to abort. "
    read -r _mm
    if [ "$_mm" = "n" ] || [ "$_mm" = "N" ]; then
      echo "Aborted."
      exit 1
    fi
  fi

  # 2. Unified ingest
  echo "→ Starting: yt_ingest_unified.py"
  INGEST_ARGS=""
  [ -n "$EFFECTIVE_FOLDER" ] && INGEST_ARGS="--folder $EFFECTIVE_FOLDER"
  [ -z "$EFFECTIVE_FOLDER" ] && [ -n "$USER_LANG" ] && INGEST_ARGS="--lang $USER_LANG"
  uv run python scripts/yt_ingest_unified.py $INGEST_ARGS $LIMIT_FLAG $DRY_RUN_FLAG

  # 2b. Dedup check — resolve duplicate dates before transcription
  echo "→ Starting: yt_review_dedup.py"
  uv run python scripts/yt_review_dedup.py --lang "$LANG" $DRY_RUN_FLAG

  # 3. Transcribe
  echo "→ Starting: transcribe.py (caffeinate, background priority)"
  TRANSCRIBE_LOG=$(mktemp)
  caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
    --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" \
    --context "$CONTEXT" --chunk-seconds 20 --created-log "$TRANSCRIBE_LOG" $LIMIT_FLAG $DRY_RUN_FLAG

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
  METADATA_LOG=$(mktemp)
  uv run python scripts/yt_metadata.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" \
    ${NAME:+--name "$NAME"} \
    --created-log "$METADATA_LOG" \
    $EXPORT_FLAGS $LIMIT_FLAG $DRY_RUN_FLAG $FORCE_FLAG

  if [ "$DRY_RUN" -eq 0 ] && [ -s "$METADATA_LOG" ]; then
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
    read -r _
  fi

  # 5. Chapters
  echo "→ Starting: yt_chapters.py"
  CHAPTERS_LOG=$(mktemp)
  CHAPTER_SOURCE_LOG_FLAG=""
  [ "$DRY_RUN" -eq 1 ] && CHAPTER_SOURCE_LOG_FLAG="--source-log $METADATA_LOG"
  uv run python scripts/yt_chapters.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" \
    --created-log "$CHAPTERS_LOG" \
    $CHAPTER_SOURCE_LOG_FLAG \
    $LIMIT_FLAG $DRY_RUN_FLAG

  if [ "$DRY_RUN" -eq 0 ] && { [ -s "$METADATA_LOG" ] || [ -s "$CHAPTERS_LOG" ]; }; then
    echo ""
    echo "----------------------------------------------------------------"
    echo "METADATA OR CHAPTERS GENERATED."
    echo "Please open reviews/${LANG_FOLDER}_review.md"
    echo "Fill Recording Date, review titles/descriptions, then press Enter."
    echo ""
    echo "OPTIONAL: set Publish Date (DD-MM-YYYY) for scheduled release."
    echo "  **Publish Date:** 15-06-2026"
    echo "  Leave empty to schedule 10 minutes from upload time."
    echo "----------------------------------------------------------------"
    read -r _

    # 5b. Dedup check — resolve any duplicates introduced after user review
    echo "→ Starting: yt_review_dedup.py (post-review check)"
    uv run python scripts/yt_review_dedup.py --lang "$LANG" $DRY_RUN_FLAG
  fi
  rm -f "$CHAPTERS_LOG"
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
  local files=()
  local f
  while IFS= read -r f; do
    [ -n "$f" ] && files+=("$f")
  done < "$log"

  if [ "${#files[@]}" -eq 0 ]; then
    echo "No files were created in this run — nothing to remove."
    return
  fi

  echo "Select files to remove before re-running:"
  local i=1
  for f in "${files[@]}"; do
    printf "  %d) %s\n" "$i" "$f"
    i=$((i + 1))
  done
  echo "Enter numbers/ranges (for example: 1,3-4), 'all', or Enter to cancel."
  printf "Remove: "
  read -r confirm_del
  if [ -z "$confirm_del" ]; then
    echo "Skipped removal — re-running without clearing existing files."
    return
  fi

  local indices=()
  if [ "$confirm_del" = "all" ] || [ "$confirm_del" = "ALL" ]; then
    for ((i = 1; i <= ${#files[@]}; i++)); do
      indices+=("$i")
    done
  else
    confirm_del=${confirm_del//,/ }
    local token start end
    for token in $confirm_del; do
      if [[ "$token" =~ ^[0-9]+-[0-9]+$ ]]; then
        start=${token%-*}
        end=${token#*-}
        if [ "$start" -le "$end" ]; then
          for ((i = start; i <= end; i++)); do indices+=("$i"); done
        else
          for ((i = start; i >= end; i--)); do indices+=("$i"); done
        fi
      elif [[ "$token" =~ ^[0-9]+$ ]]; then
        indices+=("$token")
      else
        echo "Ignoring invalid selection: $token"
      fi
    done
  fi

  local count=0
  local idx
  for idx in "${indices[@]}"; do
    if [ "$idx" -lt 1 ] || [ "$idx" -gt "${#files[@]}" ]; then
      echo "Ignoring out-of-range selection: $idx"
      continue
    fi
    f="${files[$((idx - 1))]}"
    [ -f "$f" ] && rm "$f" && count=$((count + 1))
  done
  echo "Removed $count file(s)."
}

# 6. Export (rename + embed metadata in-place)
echo "→ Starting: yt_export.py"
EXPORT_LOG=$(mktemp)
EXPORT_SOURCE_LOG_FLAG=""
[ "$DRY_RUN" -eq 1 ] && EXPORT_SOURCE_LOG_FLAG="--source-log $METADATA_LOG"
uv run python scripts/yt_export.py --lang "$LANG" \
  --folder "$EFFECTIVE_FOLDER" \
  ${NAME:+--name "$NAME"} \
  --created-log "$EXPORT_LOG" \
  $EXPORT_SOURCE_LOG_FLAG $EXPORT_FLAGS $LIMIT_FLAG $DRY_RUN_FLAG $FORCE_FLAG
rm -f "$METADATA_LOG"

# 7. Thumbnails — audio mode always; video mode only with --cover
if [ "$VIDEO_MODE" -eq 0 ] || [ "$COVER" -eq 1 ]; then
  while true; do
    THUMB_LOG=$(mktemp)
    echo "→ Starting: yt_image_gen.py"
    IMAGE_SOURCE_LOG_FLAG=""
    [ "$DRY_RUN" -eq 1 ] && IMAGE_SOURCE_LOG_FLAG="--source-log $EXPORT_LOG"
    uv run python scripts/yt_image_gen.py --lang "$LANG" \
      --folder "$EFFECTIVE_FOLDER" \
      --created-log "$THUMB_LOG" \
      $IMAGE_SOURCE_LOG_FLAG \
      $LIMIT_FLAG $DRY_RUN_FLAG $FORCE_FLAG

    if [ "$DRY_RUN" -eq 1 ]; then rm -f "$THUMB_LOG"; break; fi
    if [ ! -s "$THUMB_LOG" ]; then
      rm -f "$THUMB_LOG"
      break
    fi

    echo ""
    echo "----------------------------------------------------------------"
    echo "IMAGES GENERATED."
    THUMB_DIR="output/thumbnails${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
    echo "Review thumbnails in $THUMB_DIR"
    echo "Press Enter to continue, or 'r' to re-run image generation."
    echo "----------------------------------------------------------------"
    read -r user_input
    if [ "$user_input" != "r" ] && [ "$user_input" != "R" ]; then
      rm -f "$THUMB_LOG"
      break
    fi
    confirm_and_remove_log "$THUMB_LOG"
    rm -f "$THUMB_LOG"
  done
fi

if [ "$COVER" -eq 1 ]; then
  # 7b. Cover thumbnails — only when --cover is passed (audio or video mode)
  while true; do
    COVER_LOG=$(mktemp)
    echo "→ Starting: yt_cover_gen.py"
    COVER_SOURCE_LOG_FLAG=""
    [ "$DRY_RUN" -eq 1 ] && COVER_SOURCE_LOG_FLAG="--source-log $EXPORT_LOG"
    uv run python scripts/yt_cover_gen.py --lang "$LANG" \
      --folder "$EFFECTIVE_FOLDER" \
      --created-log "$COVER_LOG" \
      $COVER_SOURCE_LOG_FLAG \
      $LIMIT_FLAG $DRY_RUN_FLAG $FORCE_FLAG

    if [ "$DRY_RUN" -eq 1 ]; then rm -f "$COVER_LOG"; break; fi
    if [ ! -s "$COVER_LOG" ]; then
      rm -f "$COVER_LOG"
      break
    fi

    echo ""
    echo "----------------------------------------------------------------"
    echo "COVERS GENERATED."
    COVER_DIR="output/covers${EFFECTIVE_FOLDER:+/$EFFECTIVE_FOLDER}"
    echo "Review covers in $COVER_DIR"
    echo "To change cover text, edit **Suggested Title:** in reviews/${LANG_FOLDER}_review.md."
    echo "Press Enter to continue, or 'r' to remove generated covers, sync titles, and re-run cover generation."
    echo "----------------------------------------------------------------"
    read -r user_input
    if [ "$user_input" != "r" ] && [ "$user_input" != "R" ]; then
      rm -f "$COVER_LOG"
      break
    fi
    confirm_and_remove_log "$COVER_LOG"
    echo "→ Starting: yt_export.py (--sync-titles)"
    SYNC_SOURCE_LOG_FLAG=""
    [ "$DRY_RUN" -eq 1 ] && SYNC_SOURCE_LOG_FLAG="--source-log $EXPORT_LOG"
    uv run python scripts/yt_export.py --lang "$LANG" \
      --folder "$EFFECTIVE_FOLDER" \
      ${NAME:+--name "$NAME"} \
      --created-log "$EXPORT_LOG" \
      --sync-titles \
      $SYNC_SOURCE_LOG_FLAG $EXPORT_FLAGS $LIMIT_FLAG $DRY_RUN_FLAG $FORCE_FLAG
    rm -f "$COVER_LOG"
  done
fi

if [ "$VIDEO_MODE" -eq 0 ]; then
  # 8. Create MP4 videos → output/video/
  echo "→ Starting: yt_video.py"
  VIDEO_SOURCE_LOG_FLAG=""
  [ "$DRY_RUN" -eq 1 ] && VIDEO_SOURCE_LOG_FLAG="--source-log $EXPORT_LOG"
  uv run python scripts/yt_video.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" \
    $VIDEO_SOURCE_LOG_FLAG \
    $LIMIT_FLAG $DRY_RUN_FLAG $FORCE_FLAG
fi

# 9. Upload to YouTube (from output/video/)
echo "→ Starting: yt_upload.py"
UPLOAD_FILES_FLAG=""
[ "$DRY_RUN" -eq 1 ] && UPLOAD_FILES_FLAG="--files-from-log $EXPORT_LOG"
UPLOAD_BATCH_FLAG=""

if [ "$SUBFOLDER_MODE" -eq 1 ]; then
  # Subfolder mode: scan output/video/ root so files nested one level deep are included.
  uv run python scripts/yt_upload.py --lang "$LANG" \
    --input-dir "output/video/" $UPLOAD_FILES_FLAG $UPLOAD_BATCH_FLAG $LIMIT_FLAG $DRY_RUN_FLAG $FORCE_FLAG ${NAME:+--name "$NAME"}
else
  uv run python scripts/yt_upload.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" $UPLOAD_FILES_FLAG $UPLOAD_BATCH_FLAG $LIMIT_FLAG $DRY_RUN_FLAG $FORCE_FLAG ${NAME:+--name "$NAME"}
fi

if [ "$GDRIVE" -eq 1 ]; then
  # 10. Upload to Google Drive
  echo "→ Starting: gdrive_upload.py"
  GDRIVE_FILES_FLAG=""
  [ "$DRY_RUN" -eq 1 ] && GDRIVE_FILES_FLAG="--files-from-log $EXPORT_LOG"
  uv run python scripts/gdrive_upload.py --lang "$LANG" \
    --folder "$EFFECTIVE_FOLDER" $GDRIVE_FILES_FLAG $LIMIT_FLAG $DRY_RUN_FLAG
fi
rm -f "$EXPORT_LOG"

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
