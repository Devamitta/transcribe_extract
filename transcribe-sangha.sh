#!/bin/bash
# Transcribes MP3 files using MLX Whisper with Sangha-specific Pali vocabulary hints.


# 1. Transcription Phase (MLX)
echo ""
echo ">>> Audio Transcription (MLX Whisper) <<<"
# Uses caffeinate to prevent sleep and nice to lower CPU priority
caffeinate -i nice -n 10 uv run python scripts/transcribe.py --context sangha
if [ $? -ne 0 ]; then
    echo "Error during transcription. Pipeline aborted."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Transcription Completed Successfully.        "
echo "  Review 'transcribed_output' folder for transcribed text files.      "
echo "=========================================="