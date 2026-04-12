#!/bin/bash
# Transcribes MP3 files in audio/interview/ using MLX Whisper with Interview-specific Pali vocabulary hints.

# Ensure log directory exists
mkdir -p log
# Tee output to a timestamped log file in the log/ directory
LOG_FILE="log/$(basename "$0" .sh)_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo ""
echo ">>> Audio Transcription (Interview Context) <<<"
# Uses caffeinate to prevent sleep and nice to lower CPU priority
caffeinate -i nice -n 10 uv run python scripts/transcribe.py --input-dir audio/interview --output-dir output/transcribed/interview --context interview "$@"
if [ $? -ne 0 ]; then
    echo "Error during Interview transcription."
    exit 1
fi

echo ""
echo ">>> Verifying Transcription Completeness <<<"
uv run python scripts/verify_duration.py --audio-dir audio/interview --transcript-dir output/transcribed/interview
if [ $? -ne 0 ]; then
    echo "Warning: Some transcripts may be truncated. Check the report above."
fi

echo ""
echo "=========================================="
echo "  Interview Transcription Completed Successfully. "
echo "=========================================="
