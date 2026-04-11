#!/bin/bash
# Transcribes MP3 files in audio/interview/ using MLX Whisper with Interview-specific Pali vocabulary hints.

echo ""
echo ">>> Audio Transcription (Interview Context) <<<"
# Uses caffeinate to prevent sleep and nice to lower CPU priority
caffeinate -i nice -n 10 uv run python scripts/transcribe.py --input-dir audio/interview --output-dir output/transcribed/interview --context interview "$@"
if [ $? -ne 0 ]; then
    echo "Error during Interview transcription."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Interview Transcription Completed Successfully. "
echo "=========================================="
