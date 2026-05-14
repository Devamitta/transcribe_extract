#!/bin/bash
# Upload approved videos to YouTube.
# Usage: LANG=ru FOLDER=russian ./yt_upload_youtube.sh
set -e

# Validate that LANG and FOLDER are set
: "${LANG:?Set LANG=ru or LANG=en}"
: "${FOLDER:?Set FOLDER=russian or similar}"

uv run python scripts/yt_upload.py \
  --lang "$LANG" \
  --folder "$FOLDER"
