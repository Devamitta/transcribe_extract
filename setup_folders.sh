#!/bin/bash
# setup_folders.sh - Initializes the project directory structure.

# Ensure log directory exists
mkdir -p log
# Tee output to a timestamped log file in the log/ directory
LOG_FILE="log/$(basename "$0" .sh)_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo ">>> Creating directory structure <<<"

# Create audio directories
mkdir -p audio/sangha
mkdir -p audio/interview

# Create output directories
mkdir -p output/transcribed
mkdir -p output/corrected_pali
mkdir -p output/extracted

echo "Done. Folders created:"
echo " - audio/sangha (Place raw Sangha MP3s here)"
echo " - audio/interview (Place raw Interview MP3s here)"
echo " - output/transcribed (Whisper output)"
echo " - output/corrected_pali (LLM Pali correction output)"
echo " - output/extracted (Final Dhamma extraction output)"
