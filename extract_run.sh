#!/bin/bash
# Runs the Dhamma extraction pipeline with resumable stage selection.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./extract_run.sh [--from transcribe|pali|extract|polish|consolidate]

Stages:
  transcribe   transcribe audio, then run all downstream stages
  pali         Pali correction, then extract, polish, privacy, consolidate
  extract      Dhamma extraction, then polish, privacy, consolidate
  polish       polish extracted files, then privacy, consolidate
  consolidate  privacy scan, then consolidation
EOF
}

FROM_STAGE="transcribe"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --from)
      if [ "$#" -lt 2 ]; then
        echo "Error: --from requires a stage."
        usage
        exit 1
      fi
      FROM_STAGE="$2"
      shift 2
      ;;
    --from=*)
      FROM_STAGE="${1#--from=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

case "$FROM_STAGE" in
  transcribe) START_INDEX=1 ;;
  pali) START_INDEX=2 ;;
  extract) START_INDEX=3 ;;
  polish) START_INDEX=4 ;;
  consolidate) START_INDEX=5 ;;
  *)
    echo "Error: unknown --from stage '$FROM_STAGE'."
    usage
    exit 1
    ;;
esac

mkdir -p log
mkdir -p temp
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/temp/uv-cache}"
LOG_FILE="log/$(basename "$0" .sh)_$(date +%Y%m%d_%H%M%S).log"

run_pipeline() {
if [ ! -f ".env" ]; then
  echo "CRITICAL ERROR: .env file not found."
  echo "Please create it and add the provider keys required by your configured PROVIDER."
  exit 1
fi

PARTIAL=0

run_stage() {
  local label="$1"
  local allow_partial="$2"
  shift 2

  echo ""
  echo ">>> $label <<<"
  set +e
  "$@"
  local status=$?
  set -e

  if [ "$status" -eq 0 ]; then
    return 0
  fi
  if [ "$status" -eq 2 ] && [ "$allow_partial" -eq 1 ]; then
    echo "WARNING: $label completed with partial failures; continuing."
    PARTIAL=1
    return 0
  fi

  echo "ERROR: $label failed with exit code $status. Pipeline aborted."
  exit "$status"
}

if [ "$START_INDEX" -le 1 ]; then
  run_stage "STEP 1: Audio Transcription (MLX Whisper)" 0 \
    caffeinate -i uv run python scripts/transcribe.py
fi

if [ "$START_INDEX" -le 2 ]; then
  run_stage "STEP 2: Pāli Phonetic Correction" 0 \
    uv run python scripts/correct_pali.py
fi

if [ "$START_INDEX" -le 3 ]; then
  run_stage "STEP 3: Dhamma Point Extraction" 0 \
    uv run python scripts/extract_dhamma.py
fi

if [ "$START_INDEX" -le 4 ]; then
  run_stage "STEP 4: Prose Polishing" 0 \
    uv run python scripts/polish_extract.py
fi

if [ "$START_INDEX" -le 5 ]; then
  run_stage "STEP 5: Privacy Report" 1 \
    uv run python scripts/check_privacy.py
  run_stage "STEP 6: Database Consolidation" 0 \
    uv run python scripts/consolidate.py
fi

echo ""
echo "=========================================="
if [ "$PARTIAL" -eq 1 ]; then
  echo "  Pipeline completed with partial failures."
  echo "  Re-run later to resume failed files.       "
else
  echo "  Pipeline completed successfully.        "
fi
echo "  Review 'master_dhamma_database.md'      "
echo "=========================================="
}

set +e
run_pipeline 2>&1 | tee -a "$LOG_FILE"
PIPE_STATUS=${PIPESTATUS[0]}
set -e
exit "$PIPE_STATUS"
