#!/bin/bash
# Preprocesses MP3 files from audio/ by normalizing loudness, removing silence, and converting to 16kHz mono WAV in audio_processed/.

INPUT_DIR="audio"
OUTPUT_DIR="audio_processed"

mkdir -p "$OUTPUT_DIR"

# Enable nullglob to handle empty directories cleanly
shopt -s nullglob
files=("$INPUT_DIR"/*.mp3)
total_files=${#files[@]}

if [ "$total_files" -eq 0 ]; then
    echo "No MP3 files found in $INPUT_DIR."
    exit 0
fi

echo "Found $total_files files to process in $INPUT_DIR."
processed_count=0

for f in "${files[@]}"; do
    filename=$(basename -- "$f")
    name="${filename%.*}"
    out_file="$OUTPUT_DIR/${name}.wav"

    ((processed_count++))
    remaining=$((total_files - processed_count))

    if [ -f "$out_file" ]; then
        echo "Skipping $filename (already exists). $remaining files left."
        continue
    fi

    echo "Processing $filename..."
    
    # -loglevel error is added to prevent ffmpeg from spamming the terminal and hiding progress
    caffeinate -i nice -n 10 ffmpeg -loglevel error -i "$f" \
        -af "loudnorm, \
        silenceremove=stop_periods=-1:stop_duration=2:stop_threshold=-30dB" \
        -ar 16000 -ac 1 "$out_file"

    if [ $? -ne 0 ]; then
        echo "Error processing $filename"
        exit 1
    fi
    
    echo "Done with $filename. $remaining files left."
done

echo "========================================"
echo "Audio preprocessing complete."
echo "Total files evaluated: $total_files"
echo "Outputs are located in: $(pwd)/$OUTPUT_DIR"
echo "========================================"