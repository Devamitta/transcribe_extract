# Transcription Pipeline

Converts raw audio (MP3, WAV, M4A, QTA, MOV, etc.) into Markdown transcripts using MLX Whisper with context-specific Pali vocabulary prompts.

> **Requires Apple Silicon (M1/M2/M3/M4).** MLX Whisper does not run on Intel Macs or Linux.

---

## Shell Wrapper

### `scripts/cl/transcribe` — Unified CLI

```bash
./scripts/cl/transcribe [folder_name|all] [--correct] [--slow] [--context dhamma|sangha|interview|russian|vinaya]
./scripts/cl/transcribe --help
```

The single entry point for transcription. It orchestrates the pipeline for one input folder, all folders, loose files dropped directly in `input/`, or bypasses ingestion entirely for the YouTube pipeline.
- If run without `folder_name`:
    - If there are loose files directly in `input/` (not inside any subfolder), processes those: ingests to `output/audio/`, transcribes to `output/transcribed/` (context `dhamma`, unless overridden), and (with `--correct`) corrects to `output/corrected_pali/` — all at the root, not mirrored into a subfolder.
    - Otherwise, lists available subfolders in `input/` and shows usage instructions.
- `--correct` runs Phase 3 (Pāli correction) using `scripts/correct_pali.py` after transcribing.
- `--slow` switches transcription to the high-quality `mlx-community/whisper-large-v3` model and presents an interactive prompt to optionally delete an existing transcript (and its corrected version) to re-transcribe it, or transcribe only new files. Prohibited in `all` batch mode.
- `--help` prints a description and the available flags, then exits.
- Every run is logged to a timestamped file at `log/transcribe_<timestamp>.log`.
- If run with `folder_name` (e.g. `sangha`, `my-special-talks`):
    1. **Context Mapping:** If the folder name matches a valid context (`sangha`, `dhamma`, `vinaya`, `interview`, `russian`), it uses that context. Otherwise, it defaults to the `dhamma` context. Pass `--context <ctx>` to override this regardless of folder name — e.g. `transcribe interview --context russian` ingests/transcribes `input/interview/` but passes `--context russian` to `scripts/transcribe.py`.
    2. **Phase 1: Ingestion.** Runs `scripts/audio_ingest.py`. Converts non-MP3 files in `input/<folder>/` to MP3 and moves them to `output/audio/<folder>/`.
    3. **Phase 2: Transcription.** Runs `scripts/transcribe.py` directly with the detected (or overridden) context. Prints the output directory and resulting filenames when done.
    4. **Phase 2.5: Verification.** Runs `scripts/verify_duration.py` to ensure transcripts aren't truncated.
    5. **Phase 3: Pali Correction (opt-in).** Only runs if `--correct` is passed. Runs `scripts/correct_pali.py` (Pāli post-correction) and prints the output directory and resulting filenames when done. Without `--correct`, the script exits after Phase 2.5.
- If run with `folder_name` set to `all`: runs the full pipeline above in sequence for every loose file directly in `input/` (if any) and every sub-folder currently present in `input/`, stopping on the first failure. `--context`, if passed, overrides the context for every folder in the batch.

`--lang` is not a flag of this wrapper — it's only relevant to the YouTube pipeline (`yt_run.sh`), which calls `scripts/transcribe.py --lang ...` directly.

---

## Ingestion phase

`scripts/audio_ingest.py` ensures all media is in MP3 format before transcription begins.

- **Supported Formats:** MP3, WAV, M4A, AIFF, FLAC, OGG, OPUS, WMA, QTA, M4P, MP4, MKV, MOV, MPEG, MPG, WEBM.
- **Action:** Non-MP3 files are converted via `ffmpeg`, moved to `output/audio/<folder>/`, and the originals in `input/<folder>/` are removed. Existing MP3s are simply moved to `output/audio/<folder>/`.

---

## Direct Script

```bash
uv run python scripts/transcribe.py [options]
```

*Use `caffeinate -i nice -n 10` on macOS to prevent sleep and manage CPU priority.*

### Input / output resolution

| Flag combination | Input dir | Output dir |
|---|---|---|
| `--input-dir <path>` | `<path>` | `output/transcribed/<relative>` (mirrors `input/` or `output/audio/` structure) or `--output-dir` |
| `--lang ru\|en [--folder name]` | `output/audio/<folder>` | `output/transcribed/<folder>` |
| Neither | `audio/` | `output/transcribed/` |

`--output-dir` always overrides the derived output path.

### All flags

| Flag | Default | Description |
|---|---|---|
| `--input-dir <path>` | — | Explicit input directory. Overrides `--lang`/`--folder`. |
| `--output-dir <path>` | — | Explicit output directory. Overrides all derivation. |
| `--lang ru\|en` | — | Language shorthand; resolves dirs to `output/audio/<folder>` and `output/transcribed/<folder>`. |
| `--folder <name>` | lang default | Subfolder override when used with `--lang`. |
| `--context <ctx>` | `interview` | Pali vocabulary context: `sangha`, `dhamma`, `vinaya`, `interview`, `russian`. |
| `--chunk-seconds <n>` | `60` | Paragraph flush interval in seconds. Use `20` for finer YouTube chapter timestamps. |
| `--limit <n>` | `0` (no limit) | Cap processing to the first N pending files. |
| `--test-run` | off | Transcribe only the first file found. |
| `--dry-run` | off | Print what would be transcribed; create output stubs for pipeline propagation. |
| `--created-log <path>` | — | File path where created transcript paths are appended (one per line). Used internally by `scripts/cl/transcribe`. |
| `--model <name>` | `mlx-community/whisper-large-v3-turbo` | MLX Whisper model repo to use for transcription. |

### Pali vocabulary contexts

| Context | Prompt language | Typical use |
|---|---|---|
| `sangha` | English | Saṅgha meetings |
| `dhamma` | English | Dhamma classes |
| `vinaya` | English | Vinaya classes |
| `interview` | English | Meditation interviews |
| `russian` | Russian | Russian-language Dhamma talks |

### Hallucination filter

The script applies a multi-pass filter to each Whisper segment before writing it:

1. **Punctuation/character spam** — drops segments with 6+ repeated punctuation chars or 10+ repeated single chars.
2. **CJK hallucinations** — strips CJK characters while preserving English/Pali.
3. **Word loops** — drops segments where a single word repeats 4+ times (6+ for common fillers like "yeah", "okay").
4. **Phrase loops** — drops segments that duplicate a phrase already in the recent tail history.
5. **Low-entropy spam** — drops segments longer than 20 chars with fewer than 5 unique characters.
6. **Silence hallucinations** — drops short isolated filler segments ("help", "so", "yeah", etc.).

### Thermal pacing (cooldown)

Between files, the script sleeps for `max(10s, min(180s, elapsed × 0.30))` to let the chip cool down. The last file in a batch skips the cooldown.

---

## Duration verification

After each `scripts/cl/transcribe` run, `scripts/verify_duration.py` compares transcript length against the source audio to detect truncated outputs. Warnings are printed but do not abort the pipeline.
