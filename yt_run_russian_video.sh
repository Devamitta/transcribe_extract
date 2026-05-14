#!/bin/bash
# Russian YouTube pipeline (video-input mode).
# Usage: ./yt_run_russian_video.sh [folder]   default folder: russian
set -e

# Default to "russian" if no folder argument is provided
FOLDER="${1:-russian}"

# 1. Ingest video files (extract audio for transcription)
uv run python scripts/yt_ingest.py --folder "$FOLDER"

# 2. Transcribe MP3 files using MLX Whisper
# --context russian ensures correct Pali terms for Russian talks
caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
  --input-dir "audio/$FOLDER" --output-dir "output/transcribed/$FOLDER" \
  --context russian --chunk-seconds 30

# 3. Generate metadata suggestions
uv run python scripts/yt_metadata.py --lang ru --folder "$FOLDER"

# 4. Generate AI chapter timestamps
uv run python scripts/yt_chapters.py --lang ru --folder "$FOLDER"

echo ""
echo "----------------------------------------------------------------"
echo "METADATA GENERATED."
echo "Please open reviews/${FOLDER}_review.md"
echo "1. Fill in the 'Recording Date' (DD-MM-YYYY) and set 'Approved: yes' for each talk."
echo "2. Review and edit titles and descriptions."
echo "3. Press Enter here when finished to continue with export and video creation."
echo "----------------------------------------------------------------"
read -r _

# 5. Embed metadata into source .mp4 and move to upload folder
uv run python scripts/yt_export.py --folder "$FOLDER" --video-mode

# 6. Dry-run upload (YouTube)
uv run python scripts/yt_upload.py --lang ru --folder "$FOLDER" \
  --input-dir "output/${FOLDER}_video_upload" --dry-run

# 7. Dry-run upload (Google Drive)
uv run python scripts/gdrive_upload.py --lang ru --folder "$FOLDER" \
  --input-dir "output/${FOLDER}_video_upload" --dry-run

echo ""
echo "PIPELINE COMPLETE."
echo "Videos are ready in output/${FOLDER}_video_upload/"
echo "Run scripts/yt_upload.py or scripts/gdrive_upload.py (without --dry-run) to upload."
