#!/bin/bash
# Tests for YouTube pipeline --dry-run parity: verifies paths, stubs, and cleanup without real uploads.

set -euo pipefail

# ── paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_DIR=""
PASS=0
FAIL=0
FAIL_MSGS=()

# ── cleanup trap ───────────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "→ [HARNESS] Restoring output/ and reviews/..."

  # Restore backed-up directories
  if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
    [ -e output ] && mv output "$BACKUP_DIR/test_output" 2>/dev/null || true
    [ -e reviews ] && mv reviews "$BACKUP_DIR/test_reviews" 2>/dev/null || true
    [ -e "$BACKUP_DIR/original_output" ] && mv "$BACKUP_DIR/original_output" output
    [ -e "$BACKUP_DIR/original_reviews" ] && mv "$BACKUP_DIR/original_reviews" reviews
    /bin/rm -rf "$BACKUP_DIR" 2>/dev/null || true
  fi

  # Remove temp fixtures created by this harness
  rm -f temp/dummy.mp3 temp/dummy.mp4 temp/dummy.jpg temp/from_export.log temp/from_export.out
  /bin/rm -rf temp/yt_export_integration

  # Remove any dry-run state files that may have been left by aborted runs
  rm -f temp/.dry_run_active temp/.dry_run_cleanup

  # Remove input/ stubs created during dry-run tests (best-effort scan)
  for stub_file in \
    input/dummy.mp3 \
    input/dummy.mp4 \
    input/english/dummy.jpg \
    input/english/dummy.mp3 \
    input/english/dummy.mp4 \
    input/russian/dummy.mp3 \
    input/russian/dummy.mp4; do
    [ -f "$stub_file" ] && rm -f "$stub_file"
  done
  # Remove any empty dirs we may have created under input/
  for stub_dir in input/english input/russian; do
    [ -d "$stub_dir" ] && rmdir --ignore-fail-on-non-empty "$stub_dir" 2>/dev/null || true
  done

  echo "→ [HARNESS] Cleanup done."
}
trap cleanup EXIT

# ── helpers ────────────────────────────────────────────────────────────────────
pass() {
  PASS=$((PASS + 1))
  echo "  ✓ $1"
}

fail() {
  FAIL=$((FAIL + 1))
  FAIL_MSGS+=("$1")
  echo "  ✗ $1"
}

assert_contains() {
  local label="$1"
  local haystack="$2"
  local needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    pass "$label"
  else
    fail "$label — expected to find: $needle"
  fi
}

assert_not_contains() {
  local label="$1"
  local haystack="$2"
  local needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    fail "$label — unexpectedly found: $needle"
  else
    pass "$label"
  fi
}

assert_file_exists() {
  local label="$1"
  local path="$2"
  if [ -f "$path" ]; then
    pass "$label"
  else
    fail "$label — file not found: $path"
  fi
}

assert_file_absent() {
  local label="$1"
  local path="$2"
  if [ ! -f "$path" ]; then
    pass "$label"
  else
    fail "$label — file should not exist: $path"
  fi
}

run_test() {
  local name="$1"
  echo ""
  echo "── $name ──"
}

run_pipeline() {
  OUTPUT=$(./yt_run.sh "$@" 2>&1) || true
}

run_python() {
  OUTPUT=$(uv run python "$@" 2>&1) || true
}

create_review_fixture() {
  local review_path="$1"
  local source_name="$2"
  local title="$3"
  local date="$4"
  mkdir -p "$(dirname "$review_path")"
  printf '%s\n' \
    "# English Audio Metadata Review (test)" \
    "Dry run fixture." \
    "" \
    "--- " \
    "## Source: $source_name" \
    "**Recording Date:** $date" \
    "**Approved:** yes" \
    "**Media:** audio" \
    "**Channel Playlist Overview:** Meditation, Personal" \
    "**Selected Playlist:** Meditation, Personal" \
    "**Suggested Title:** $title" \
    "**Suggested Description:** Test description." \
    "" \
    "**Suggested Tags:** #dhamma" \
    > "$review_path"
}

# ── setup: backup state ────────────────────────────────────────────────────────
echo "→ [HARNESS] Backing up output/ and reviews/..."
BACKUP_DIR=$(mktemp -d)
mv output "$BACKUP_DIR/original_output"
mv reviews "$BACKUP_DIR/original_reviews"
echo "→ [HARNESS] Backup created at $BACKUP_DIR"

mkdir -p output reviews

# ── setup: generate dummy media fixtures ───────────────────────────────────────
echo "→ [HARNESS] Generating dummy media fixtures..."
mkdir -p temp

ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 1 -q:a 9 -acodec libmp3lame \
  temp/dummy.mp3 -loglevel error
assert_file_exists "dummy.mp3 generated" temp/dummy.mp3

ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -f lavfi -i color=c=black:s=1280x720:r=25 \
  -t 1 -shortest \
  -c:v libx264 -c:a aac \
  temp/dummy.mp4 -loglevel error
assert_file_exists "dummy.mp4 generated" temp/dummy.mp4

ffmpeg -y -f lavfi -i color=c=black:s=1280x720 -frames:v 1 temp/dummy.jpg -loglevel error
assert_file_exists "dummy.jpg generated" temp/dummy.jpg

# ── tests: dry-run parity matrix ───────────────────────────────────────────────
run_test "audio root mode"
run_pipeline --dry-run dummy.mp3
assert_contains "root stub created" "$OUTPUT" "→ [DRY RUN] Stub created: input/dummy.mp3"
assert_contains "root audio ingest path" "$OUTPUT" "input/dummy.mp3 → output/audio/dummy.mp3"
assert_contains "root transcript path" "$OUTPUT" "output/audio/dummy.mp3 → output/transcribed/dummy.md"
assert_contains "root upload queues one video" "$OUTPUT" "1 video(s) queued for YouTube upload."
assert_contains "root upload title includes default speaker" "$OUTPUT" "Title:          [DRY_RUN] dummy | Bhikkhu Devamitta"
assert_contains "root cleanup runs" "$OUTPUT" "→ [DRY RUN] Cleaning up stubs..."
assert_file_absent "root input stub cleaned" input/dummy.mp3
assert_not_contains "root dry-run review entry cleaned" "$(cat reviews/english_review.md 2>/dev/null || true)" "[DRY_RUN]"

run_test "audio folder/lang mode"
run_pipeline --lang en --dry-run dummy.mp3
assert_contains "folder stub created" "$OUTPUT" "→ [DRY RUN] Stub created: input/english/dummy.mp3"
assert_contains "folder audio ingest path" "$OUTPUT" "input/english/dummy.mp3 → output/audio/english/dummy.mp3"
assert_contains "folder transcript path" "$OUTPUT" "output/audio/english/dummy.mp3 → output/transcribed/english/dummy.md"
assert_contains "folder upload sees generated mp4 dir" "$OUTPUT" "File:           output/video/english/2000-01-01 - [DRY_RUN]"
assert_contains "folder upload title includes default speaker" "$OUTPUT" "Title:          [DRY_RUN] dummy | Bhikkhu Devamitta"
assert_file_absent "folder input stub cleaned" input/english/dummy.mp3
assert_not_contains "folder dry-run review entry cleaned" "$(cat reviews/english_review.md 2>/dev/null || true)" "[DRY_RUN]"

run_test "russian default speaker"
run_pipeline --lang ru --dry-run dummy.mp3
assert_contains "russian folder stub created" "$OUTPUT" "→ [DRY RUN] Stub created: input/russian/dummy.mp3"
assert_contains "russian upload title includes default speaker" "$OUTPUT" "Title:          [DRY_RUN] dummy | Бхиккху Дэвамитта"
assert_file_absent "russian input stub cleaned" input/russian/dummy.mp3
assert_not_contains "russian dry-run review entry cleaned" "$(cat reviews/russian_review.md 2>/dev/null || true)" "[DRY_RUN]"

run_test "release privacy flag"
run_pipeline --lang en --dry-run dummy.mp3
assert_contains "default dry-run is private" "$OUTPUT" "Privacy status: private"
run_pipeline --lang en --dry-run dummy.mp3
assert_contains "second dry-run remains private" "$OUTPUT" "Privacy status: private"

run_test "video mode"
run_pipeline --lang en --video-mode --dry-run dummy.mp4
assert_contains "video stub created" "$OUTPUT" "→ [DRY RUN] Stub created: input/english/dummy.mp4"
assert_contains "video ingest output path" "$OUTPUT" "→ video: output/video/english/dummy.mp4"
assert_not_contains "video mode skips audio video generation" "$OUTPUT" "→ Starting: yt_video.py"
assert_not_contains "video mode skips thumbnail generation without cover" "$OUTPUT" "→ Starting: yt_image_gen.py"
assert_contains "video upload sees source mp4 dir" "$OUTPUT" "File:           output/video/english/2000-01-01 - [DRY_RUN]"
assert_contains "video upload sees source mp4 name" "$OUTPUT" "dummy - Bhikkhu Devamitta.mp4"
assert_file_absent "video input stub cleaned" input/english/dummy.mp4

run_test "video mode with cover"
run_pipeline --lang en --video-mode --cover --dry-run dummy.mp4
assert_contains "video cover mode runs thumbnail generation" "$OUTPUT" "→ Starting: yt_image_gen.py"
assert_contains "video cover mode runs cover generation" "$OUTPUT" "→ Starting: yt_cover_gen.py"
assert_contains "video cover output dir" "$OUTPUT" "output/covers/english/2000-01-01 - [DRY_RUN]"
assert_contains "video cover output name" "$OUTPUT" "dummy - Bhikkhu Devamitta.jpg"
assert_not_contains "video cover mode still skips audio video generation" "$OUTPUT" "→ Starting: yt_video.py"

run_test "image ingest cover dry-run"
mkdir -p input/english temp
cp temp/dummy.jpg input/english/dummy.jpg
touch temp/.dry_run_active
> temp/.dry_run_cleanup
run_python scripts/yt_ingest_unified.py --folder english --cover --dry-run
assert_contains "image dry-run reports thumbnail" "$OUTPUT" "input/english/dummy.jpg → output/thumbnails/english/dummy.jpg"
assert_contains "image dry-run reports cover" "$OUTPUT" "input/english/dummy.jpg → output/covers/english/dummy.jpg"
assert_file_exists "image thumbnail stub exists" output/thumbnails/english/dummy.jpg
assert_file_exists "image cover stub exists" output/covers/english/dummy.jpg
rm -f temp/.dry_run_active temp/.dry_run_cleanup input/english/dummy.jpg

run_test "from-export compatibility mode"
mkdir -p output/audio/english output/transcribed/english
> output/audio/english/dummy.mp3
> output/transcribed/english/dummy.md
create_review_fixture reviews/english_review.md dummy.md "[DRY_RUN] From Export Fixture" "02-01-2026"
run_pipeline --lang en --from-export --dry-run
assert_contains "from-export reports deprecation" "$OUTPUT" "→ --from-export is deprecated; running the resumable pipeline from the beginning."
assert_contains "from-export runs ingest" "$OUTPUT" "→ Starting: yt_ingest_unified.py"
assert_contains "from-export runs transcribe" "$OUTPUT" "→ Starting: transcribe.py"
assert_contains "from-export runs metadata" "$OUTPUT" "→ Starting: yt_metadata.py"
assert_contains "from-export runs chapters" "$OUTPUT" "→ Starting: yt_chapters.py"
assert_contains "from-export runs export" "$OUTPUT" "→ Starting: yt_export.py"
assert_contains "from-export runs upload" "$OUTPUT" "→ Starting: yt_upload.py"
assert_not_contains "from-export does not use folder as playlist" "$OUTPUT" "Playlist:       english"

run_test "ariyadhammika video mode"
run_pipeline --name "Ariyadhammika Bhikkhu" --video-mode --dry-run dummy.mp4
assert_contains "ariyadhammika cleanup runs" "$OUTPUT" "→ [DRY RUN] Cleaning up stubs..."
assert_contains "ariyadhammika keeps default title path" "$OUTPUT" "File:           output/video/2000-01-01 - [DRY_RUN] dummy.mp4"
assert_not_contains "ariyadhammika video mode skips audio video generation" "$OUTPUT" "→ Starting: yt_video.py"

run_test "force video mode"
run_pipeline --name "Ariyadhammika Bhikkhu" --video-mode --force --dry-run dummy.mp4
assert_contains "force dry-run accepts force flag" "$OUTPUT" "→ [DRY RUN] Cleaning up stubs..."
assert_contains "force dry-run queues upload" "$OUTPUT" "video(s) queued for YouTube upload."

# ── tests: local integration export ────────────────────────────────────────────
run_test "yt_export direct ffmpeg integration"
mkdir -p temp/yt_export_integration/output/video/english \
  temp/yt_export_integration/output/transcribed/english \
  temp/yt_export_integration/reviews
cp temp/dummy.mp4 temp/yt_export_integration/output/video/english/dummy.mp4
printf '[0.0] Test transcript.\n' > temp/yt_export_integration/output/transcribed/english/dummy.md
create_review_fixture temp/yt_export_integration/reviews/english_review.md dummy.md "Export Integration Fixture" "03-01-2026"
(
  cd temp/yt_export_integration
  mkdir -p output/audio/english
  PYTHONPATH="$PROJECT_ROOT" uv --project "$PROJECT_ROOT" run python "$PROJECT_ROOT/scripts/yt_export.py" \
    --lang en --folder english --video-mode \
    --review-file reviews/english_review.md \
    > from_export.out 2>&1
) || true
assert_file_exists "integration exported renamed mp4 exists" temp/yt_export_integration/output/video/english/2026-01-03\ -\ Export\ Integration\ Fixture.mp4
if ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 \
  temp/yt_export_integration/output/video/english/2026-01-03\ -\ Export\ Integration\ Fixture.mp4 >/dev/null 2>&1; then
  pass "integration exported mp4 is valid"
else
  fail "integration exported mp4 is valid — ffprobe could not read file"
fi

# ── summary ────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
echo "Results: $PASS passed, $FAIL failed"
if [ "${#FAIL_MSGS[@]}" -gt 0 ]; then
  echo ""
  echo "Failures:"
  for msg in "${FAIL_MSGS[@]}"; do
    echo "  ✗ $msg"
  done
fi
echo "══════════════════════════════════════"

[ "$FAIL" -eq 0 ]
