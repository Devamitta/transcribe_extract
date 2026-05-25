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
mkdir -p output/covers

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

# Bio link appended to YouTube descriptions (leave empty for no bio)
BIO_EN=
BIO_RU=

# yt_cover_gen.py — YouTube cover thumbnail text overlay
COVER_GRADIENT_HEIGHT_PCT=0.45
COVER_GRADIENT_MAX_ALPHA=200
COVER_BOTTOM_GRADIENT_HEIGHT_PCT=0.20
COVER_FONT_PATH='/System/Library/Fonts/Avenir Next.ttc'
COVER_RU_FONT_PATH='/System/Library/Fonts/Avenir Next.ttc'
COVER_TITLE_SIZE_PCT=0.33
COVER_TITLE_STROKE_PCT=0.10
COVER_TEACHER_SIZE_PCT=0.07
COVER_TEXT_X_PCT=0.04
COVER_MAX_TEXT_W_PCT=0.85
COVER_SHADOW_OFFSET=1
EOF
    echo ".env template created — fill in your API keys before running pipelines."
else
    echo ".env already exists — skipped."
fi
