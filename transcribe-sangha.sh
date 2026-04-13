#!/bin/bash
# Transcribes MP3 files in audio/sangha/ using MLX Whisper with Sangha-specific Pali vocabulary hints.

# Ensure log directory exists
mkdir -p log
# Tee output to a timestamped log file in the log/ directory
LOG_FILE="log/$(basename "$0" .sh)_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo ""
echo ">>> Audio Transcription (Sangha Context) <<<"
# Uses caffeinate to prevent sleep
caffeinate -i uv run python scripts/transcribe.py --input-dir audio/sangha --output-dir output/transcribed/sangha --context sangha "$@"
if [ $? -ne 0 ]; then
    echo "Error during Sangha transcription."
    exit 1
fi

echo ""
echo ">>> Verifying Transcription Completeness <<<"
uv run python scripts/verify_duration.py --audio-dir audio/sangha --transcript-dir output/transcribed/sangha
if [ $? -ne 0 ]; then
    echo "Warning: Some transcripts may be truncated. Check the report above."
fi

echo ""
echo "=========================================="
echo "  Sangha Transcription Completed Successfully. "
echo "=========================================="
