#!/bin/bash
# Full automated pipeline for Tims Dhamma talks: Transcription -> Pali Correction -> Metadata -> Export.

# 1. Warning & User Confirmation
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
echo "  WARNING: Please ensure 'audio/tims/' contains ONLY the files"
echo "  you wish to process in this batch. Remove any old files first."
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
read -p "Press Enter to continue or Ctrl+C to abort..."

# 2. Setup Logging
mkdir -p log
LOG_FILE="log/tims_pipeline_$(date +%Y%m%d_%H%M%S).log"
# Use a subshell to tee everything to the log file while still showing it in the terminal
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Pipeline started at $(date)"

# Step 1: Transcription
echo ""
echo ">>> Step 1: Transcription <<<"
mkdir -p output/transcribed/tims

# Note: Uses caffeinate to prevent sleep on macOS
caffeinate -i uv run python scripts/transcribe.py --input-dir audio/tims --output-dir output/transcribed/tims --context dhamma "$@"
if [ $? -ne 0 ]; then
    echo "Error during transcription."
    exit 1
fi

echo "Verifying transcription completeness..."
uv run python scripts/verify_duration.py --audio-dir audio/tims --transcript-dir output/transcribed/tims
if [ $? -ne 0 ]; then
    echo "Warning: Some transcripts may be truncated. Check the report above."
fi

# Step 2: Pali Correction
echo ""
echo ">>> Step 2: Pali Correction <<<"
mkdir -p output/corrected_pali/tims

PYTHONPATH=. uv run python scripts/correct_pali.py output/transcribed/tims/
if [ $? -ne 0 ]; then
    echo "Error during Pali correction."
    exit 1
fi

# Step 3: Metadata Generation
echo ""
echo ">>> Step 3: Metadata Generation <<<"
# We keep old review files but look for the latest one below.
# The metadata script itself will generate a new one with a date.

PYTHONPATH=. uv run python scripts/tims_metadata.py
if [ $? -ne 0 ]; then
    echo "Error during metadata generation."
    exit 1
fi

# Identify the latest generated review file
REVIEW_FILE=$(ls -t output/tims_review_*.md 2>/dev/null | head -n 1)

if [ -z "$REVIEW_FILE" ]; then
    echo "Error: Metadata review file not found."
    exit 1
fi

echo ""
echo "----------------------------------------------------------------"
echo "  PAUSE: Metadata generated: $REVIEW_FILE"
echo "  You can now review/edit the suggestions in the file above"
echo "  before proceeding to the final export and tagging step."
echo "----------------------------------------------------------------"
read -p "Press Enter to proceed with EXPORT or Ctrl+C to abort..."

# Step 4: Export & Tagging
echo ""
echo ">>> Step 4: Export and Metadata Tagging <<<"
mkdir -p output/audio_youtube

PYTHONPATH=. uv run python scripts/tims_export.py --review-file "$REVIEW_FILE"
if [ $? -ne 0 ]; then
    echo "Error during export script."
    exit 1
fi

echo ""
echo "================================================="
echo "  TIMS FULL PIPELINE COMPLETED SUCCESSFULLY. "
echo "  Final files ready in 'output/audio_youtube/'."
echo "================================================="
