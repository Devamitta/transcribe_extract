#!/bin/bash
# Transcribes MP3 files in audio/sangha/ using MLX Whisper with Sangha-specific Pali vocabulary hints.

echo ""
echo ">>> Audio Transcription (Sangha Context) <<<"
# Uses caffeinate to prevent sleep and nice to lower CPU priority
caffeinate -i nice -n 10 uv run python scripts/transcribe.py --input-dir audio/sangha --context sangha "$@"
if [ $? -ne 0 ]; then
    echo "Error during Sangha transcription."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Sangha Transcription Completed Successfully. "
echo "=========================================="
