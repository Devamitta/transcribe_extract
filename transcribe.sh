#!/bin/bash

echo "=========================================="
echo "  Transcription Initialized             "
echo "=========================================="


# 1. Transcription Phase (MLX)
echo ""
echo ">>> Audio Transcription (MLX Whisper) <<<"
# Uses caffeinate to prevent sleep and nice to lower CPU priority
caffeinate -i nice -n 10 uv run python scripts/transcribe.py
if [ $? -ne 0 ]; then
    echo "Error during transcription. Pipeline aborted."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Transcription Completed Successfully.        "
echo "  Review 'transcribed_output' folder for transcribed text files.      "
echo "=========================================="