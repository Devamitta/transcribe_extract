#!/bin/bash
# Unified transcription script; runs one or all contexts (sangha, interview, dhamma).
# Usage: ./transcribe.sh [--context sangha|interview|dhamma] [extra args for transcribe.py]

CONTEXT=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context) CONTEXT="$2"; shift 2 ;;
    *) EXTRA_ARGS+=("$1"); shift ;;
  esac
done

mkdir -p log
LOG_FILE="log/$(basename "$0" .sh)_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

run_context() {
  local ctx="$1"
  echo ""
  echo ">>> Audio Transcription (${ctx} context) <<<"
  if ! caffeinate -i uv run python scripts/transcribe.py \
    --input-dir "input/${ctx}" \
    --context "$ctx" \
    "${EXTRA_ARGS[@]}"; then
    echo "Error during ${ctx} transcription."
    return 1
  fi
  echo ""
  echo ">>> Verifying Transcription Completeness <<<"
  if ! uv run python scripts/verify_duration.py \
    --audio-dir "input/${ctx}"; then
    echo "Warning: Some transcripts may be truncated. Check the report above."
  fi
}

VALID_CONTEXTS=(sangha interview dhamma)

if [ -n "$CONTEXT" ]; then
  valid=0
  for c in "${VALID_CONTEXTS[@]}"; do
    [ "$c" = "$CONTEXT" ] && valid=1
  done
  if [ "$valid" -eq 0 ]; then
    echo "Usage: ./transcribe.sh [--context sangha|interview|dhamma] [extra args for transcribe.py]"
    exit 1
  fi
  run_context "$CONTEXT" || exit 1
else
  echo ">>> Starting Batch Transcription Pipeline <<<"
  for ctx in "${VALID_CONTEXTS[@]}"; do
    run_context "$ctx" || { echo "${ctx} transcription failed. Stopping batch."; exit 1; }
  done
  echo ""
  echo "=========================================="
  echo "  Batch Transcription Pipeline Complete.  "
  echo "=========================================="
fi
