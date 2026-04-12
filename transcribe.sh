#!/bin/bash
# Batch transcription script that processes Sangha and Interview folders sequentially.

# Ensure log directory exists
mkdir -p log
# Tee output to a timestamped log file in the log/ directory
LOG_FILE="log/$(basename "$0" .sh)_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo ">>> Starting Batch Transcription Pipeline <<<"

./transcribe-sangha.sh "$@"
if [ $? -ne 0 ]; then
    echo "Sangha transcription failed. Stopping batch."
    exit 1
fi

./transcribe-interview.sh "$@"
if [ $? -ne 0 ]; then
    echo "Interview transcription failed. Stopping batch."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Batch Transcription Pipeline Complete.  "
echo "=========================================="
