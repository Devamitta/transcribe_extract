#!/bin/bash
# Runs the full Dhamma extraction pipeline: transcription, Pāli correction, Dhamma point extraction, and database consolidation.

# Ensure log directory exists
mkdir -p log
# Tee output to a timestamped log file in the log/ directory
LOG_FILE="log/$(basename "$0" .sh)_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

# 1. Environment Safety Check
if [ ! -f ".env" ]; then
    echo "CRITICAL ERROR: .env file not found."
    echo "Please create it and add GEMINI_API_KEY before running."
    exit 1
fi

# 2. Transcription Phase (MLX)
echo ""
echo ">>> STEP 1: Audio Transcription (MLX Whisper) <<<"
# Uses caffeinate to prevent sleep
caffeinate -i uv run python scripts/transcribe.py
if [ $? -ne 0 ]; then
    echo "Error during transcription. Pipeline aborted."
    exit 1
fi

# 3. Correction Phase (Gemini API Pass 1)
echo ""
echo ">>> STEP 2: Pāli Phonetic Correction <<<"
uv run python scripts/check_keys.py --text
if [ $? -ne 0 ]; then
    echo "Error during model preflight. Pipeline aborted."
    exit 1
fi
uv run python scripts/correct_pali.py
if [ $? -ne 0 ]; then
    echo "Error during Pāli correction. Pipeline aborted."
    exit 1
fi

# 4. Extraction Phase (Gemini API Pass 2)
echo ""
echo ">>> STEP 3: Dhamma Point Extraction <<<"
uv run python scripts/extract_dhamma.py
if [ $? -ne 0 ]; then
    echo "Error during point extraction. Pipeline aborted."
    exit 1
fi

# 5. Consolidation Phase
echo ""
echo ">>> STEP 4: Database Consolidation <<<"
uv run python scripts/consolidate.py
if [ $? -ne 0 ]; then
    echo "Error during consolidation. Pipeline aborted."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Pipeline Completed Successfully.        "
echo "  Review 'master_dhamma_database.md'      "
echo "=========================================="
