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

_has_arg() {
  local needle="$1"; shift
  for a in "$@"; do [[ "$a" == "$needle" ]] && return 0; done
  return 1
}

run_context() {
  local ctx="$1"
  local transcribe_log
  transcribe_log=$(mktemp)
  echo ""
  echo ">>> Audio Transcription (${ctx} context) <<<"

  local dir_arg=()
  if ! _has_arg "--input-dir" "${EXTRA_ARGS[@]}" && ! _has_arg "--lang" "${EXTRA_ARGS[@]}"; then
    dir_arg=(--input-dir "input/${ctx}")
  fi

  if ! caffeinate -i uv run python scripts/transcribe.py \
    "${dir_arg[@]}" \
    --context "$ctx" \
    --created-log "$transcribe_log" \
    "${EXTRA_ARGS[@]}"; then
    echo "Error during ${ctx} transcription."
    rm -f "$transcribe_log"
    return 1
  fi
  echo ""
  echo ">>> Verifying Transcription Completeness <<<"
  if ! uv run python scripts/verify_duration.py \
    --audio-dir "input/${ctx}" \
    --created-log "$transcribe_log"; then
    echo "Warning: Some transcripts may be truncated. Check the report above."
  fi
  rm -f "$transcribe_log"
}

# --lang bypasses the context loop — pass directly to transcribe.py (YouTube pipeline mode)
if _has_arg "--lang" "${EXTRA_ARGS[@]}"; then
  transcribe_log=$(mktemp)
  caffeinate -i uv run python scripts/transcribe.py \
    --created-log "$transcribe_log" \
    "${EXTRA_ARGS[@]}"
  EXIT_CODE=$?
  rm -f "$transcribe_log"
  exit $EXIT_CODE
fi

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
