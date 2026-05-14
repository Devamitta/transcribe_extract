#!/bin/bash
# Full English YouTube pipeline (audio-input mode).
# Usage: ./yt_run_english.sh [folder]   default folder: english
set -e

# Default to "english" if no folder argument is provided
FOLDER="${1:-english}"

# 1. Convert non-MP3 audio to MP3 in-place
uv run python scripts/yt_audio_convert.py --folder "$FOLDER"

# 2. Transcribe MP3 files using MLX Whisper
# --context dhamma or sangha or vinaya or interview for English talks
caffeinate -i nice -n 10 uv run python scripts/transcribe.py \
  --input-dir "audio/$FOLDER" --output-dir "output/transcribed/$FOLDER" \
  --context dhamma --chunk-seconds 30

# 3. Generate metadata suggestions
uv run python scripts/yt_metadata.py  --lang en --folder "$FOLDER"

# 4. Generate AI chapter timestamps
uv run python scripts/yt_chapters.py  --lang en --folder "$FOLDER"

echo ""
echo "----------------------------------------------------------------"
echo "METADATA GENERATED."
echo "Please open reviews/${FOLDER}_review.md"
echo "1. Fill in the 'Recording Date' (DD-MM-YYYY) for approved talks."
echo "2. Review and edit titles and descriptions."
echo "3. Press Enter here when finished to continue with export and video creation."
echo "----------------------------------------------------------------"
read -r _

# 5. Rename files by date and export with metadata
uv run python scripts/yt_export.py    --folder "$FOLDER"

# 6. Generate thumbnail images
uv run python scripts/yt_image_gen.py --lang en --folder "$FOLDER"

# 7. Create MP4 videos
uv run python scripts/yt_video.py     --folder "$FOLDER"

echo ""
echo "PIPELINE COMPLETE."
echo "Videos are ready in output/${FOLDER}_youtube/"
echo "Run scripts/yt_upload.py or scripts/gdrive_upload.py to upload."
