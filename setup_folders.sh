#!/bin/bash
# setup_folders.sh - Initializes the project directory structure.

# Ensure log directory exists
mkdir -p log
# Tee output to a timestamped log file in the log/ directory
LOG_FILE="log/$(basename "$0" .sh)_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo ">>> Creating directory structure <<<"

# Input staging directory
mkdir -p input

# Namespaced output directories
mkdir -p output/audio
mkdir -p output/video
mkdir -p output/thumbnails

# Output directories — transcription & correction
mkdir -p output/transcribed
mkdir -p output/corrected_pali
mkdir -p output/extracted
mkdir -p output/polished

# Output directories — batch pipeline
mkdir -p output/batch_input

# Reports and reviews
mkdir -p reports/semantic
mkdir -p reviews

# Scratch space (gitignored)
mkdir -p temp

echo "Done. Folders created."

# Create .env template if it doesn't exist
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# LLM provider: openrouter | gemini | openai | deepseek
PROVIDER=
IMAGE_PROVIDER=

# API keys — fill in the one matching your PROVIDER
OPENROUTER_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
DEEPSEEK_API_KEY=

# Google Drive upload — folder IDs from Drive URL
GDRIVE_FOLDER_ID_RU=
GDRIVE_FOLDER_ID_EN=
EOF
    echo ".env template created — fill in your API keys before running pipelines."
else
    echo ".env already exists — skipped."
fi
