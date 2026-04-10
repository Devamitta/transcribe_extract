#!/bin/bash
# Batch transcription script that processes Sangha and Interview folders sequentially.

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
