# Dhamma Transcriber & Extractor

A local pipeline that converts MP3 Dhamma talks into Markdown transcripts using MLX Whisper (Apple Silicon), then extracts core Dhamma points using Google Gemini API or OpenRouter.

The repository primarily functions as a transcription engine followed by extraction of Dhamma-Vinaya content.

---

## 0. Prerequisites & Installation

Before running the pipeline, ensure you have the following installed on your macOS (Apple Silicon recommended):

### 1. Install Homebrew
If you don't have Homebrew, install it first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install System Dependencies
Transcription requires `ffmpeg` for audio processing:
```bash
brew install ffmpeg
```

### 3. Install `uv`
We use `uv` for fast Python dependency management:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 4. Setup Project & Dependencies
Once `uv` is installed, run the following command in the project root to install the correct Python version and all dependencies:
```bash
uv sync
```
*Note: Run `uv sync` whenever you pull new changes to ensure your environment is up to date.*

---

## 1. Transcription

The transcription phase converts raw audio into Markdown format, using context-specific Pali glossaries to improve accuracy.

### Transcription Options

You can run transcription for specific contexts or as a batch:

| Scope | Command | Input Directory | Output Directory |
| :--- | :--- | :--- | :--- |
| **All** | `./transcribe.sh` | `audio/sangha/` & `audio/interview/` | `output/transcribed/` |
| **Saṅgha** | `./transcribe-sangha.sh` | `audio/sangha/` | `output/transcribed/sangha/` |
| **Interview** | `./transcribe-interview.sh` | `audio/interview/` | `output/transcribed/interview/` |

### Manual Execution (`scripts/transcribe.py`)

For more control, you can run the Python script directly:

```bash
uv run python scripts/transcribe.py --input-dir <dir> --output-dir <dir> --context <context>
```

**Options:**
- `--input-dir`: Directory containing raw `.mp3` files.
- `--output-dir`: Where to save the generated `.md` files.
- `--context`: Select vocabulary context: `sangha`, `dhamma`, `vinaya`, or `interview`.
- `--test-run`: Transcribe only the first file found (for quick testing).

*Note: It is recommended to use `caffeinate -i nice -n 10` before the command on macOS to prevent sleep and manage CPU priority.*

---

## 2. Transcription Quality Implementation Loop

To maintain and improve transcription quality, we use an iterative feedback loop to identify and filter "fuzzies" (Whisper hallucinations, phrase loops, and anomalies).

Detailed logs and progress of this loop are tracked in: `kamma/threads/ongoing_transcription_feedback/`

### How to Run the Quality Loop

The loop consists of identifying anomalies in the latest output and refining the filters.

#### Step 1: Extract Anomalies (Fuzzies)
Run the error extraction tool on your latest transcription output to find potential hallucinations or loops.

```bash
uv run python scripts/extract_errors.py --input-dir output/transcribed/sangha/
```
This generates a report (usually in `reports/`) detailing repeated phrases and suspicious sequences with their surrounding context.

#### Step 2: Compare with Baselines
If you have made changes to the filters in `scripts/transcribe.py`, compare the new report with a previous one to verify improvements.

```bash
uv run python scripts/diff_reports.py log/old_report.md log/new_report.md
```

#### Step 3: Manual Verification
To manually verify if an anomaly is a real hallucination or just a natural stutter, you can extract the specific audio snippet:

```bash
uv run python scripts/extract_snippets.py log/report_20260411.md
```
This saves short audio clips corresponding to each anomaly in the report for easy listening.

#### Step 4: Refine Filters
Based on the reports, update the hallucination filters in `scripts/transcribe.py`. We use punctuation-agnostic checks and tiered repetition detection to distinguish between natural speech stutters and Whisper glitches.

#### Step 5: Verify
Rerun the transcription on the problematic files to ensure the "fuzzies" are now correctly skipped or handled.

---

## 3. Pali Spelling Correction

The `scripts/correct_pali.py` tool refines the spelling of Pāli terms in the transcripts using a consolidated glossary of ~155 terms synchronized with the transcription engine's vocabulary.

### Features
- **Phonetic Correction:** Fixes common phonetic misspellings (e.g., "sangha" -> "Saṅgha", "nibbana" -> "nibbāna").
- **Recursive Processing:** By default, scans `output/transcribed/` recursively and preserves the subfolder structure in the output.
- **Constrained AI Engine:** Uses a highly optimized prompt to ensure only Pāli terms are corrected while surrounding English text, punctuation, and formatting remain 100% unchanged.

### Usage

**Process all transcripts:**
```bash
PYTHONPATH=. uv run python scripts/correct_pali.py
```

**Process a specific file or folder:**
```bash
PYTHONPATH=. uv run python scripts/correct_pali.py <filename_or_path>
```

The corrected files will be saved in `output/corrected_pali/`, mirroring the input directory structure.

---

## 4. Tims YouTube Pipeline

A two-step pipeline for generating and packaging YouTube upload metadata for Tims Dhamma talks.
Input: corrected Pāli transcripts from `output/corrected_pali/tims/`.

### Step 1: Generate Metadata Suggestions

Reads each corrected transcript and uses the LLM to suggest a YouTube title and upload description.

**Batch mode (all files):**
```bash
PYTHONPATH=. uv run python scripts/tims_metadata.py
```

**Single-file test mode:**
```bash
PYTHONPATH=. uv run python scripts/tims_metadata.py --file "output/corrected_pali/tims/<filename>.md"
```

Output: `output/tims_review_YYYY-MM-DD.md` — a combined markdown review file containing, for each talk:
- Original filename
- Suggested title
- Suggested description

**Options:**
- `--file <path>`: process a single file only (test mode)
- `--input-dir <path>`: override input directory (default: `output/corrected_pali/tims`)
- `--output-file <path>`: override output review file path
- `--test` / `-t`: use provider test models

### Step 2: Human Review

Open `output/tims_review_YYYY-MM-DD.md` and edit the suggested titles and descriptions as needed.
The export script treats whatever is in this file as the approved values — it is the source of truth.

### Automated Full Pipeline (`tims_pipeline.sh`)

For processing a new batch of Tims talks, you can run the full automated pipeline:

```bash
./tims_pipeline.sh
```

This script handles all steps sequentially and supports incremental processing (skips existing files):
1.  **Transcription:** Processes any new files in `audio/tims/` into `output/transcribed/tims/`.
2.  **Pāli Correction:** Corrects new transcripts into `output/corrected_pali/tims/`.
3.  **Metadata Generation:** Generates a new metadata review file `output/tims_review_YYYY-MM-DD.md`.
4.  **Pause for Review:** Allows you to edit the generated review file before proceeding.
5.  **Export & Tagging:** Packages approved audio into `output/audio_youtube/` with metadata tags (Artist: Devamitta Bhikkhu, Title: [Talk Title]) and verifies the file count.


---

## 4.5 Semantic Evaluation (Quality Control)

After Pali correction, the semantic evaluator detects remaining Whisper hallucinations and contextually wrong passages that could degrade Dhamma extraction quality. This stage catches English-word substitutions and garbled terms that the Pali correction step missed.

### Direct Mode (Real-Time)

Evaluate corrected transcripts from a specific folder:

```bash
uv run python scripts/evaluate_semantic.py interview
```

This generates a timestamped report in `reports/semantic_anomalies_<timestamp>.md` listing findings with passages, issues, and suggestions.

**Options:**
- Specify a folder: `uv run python scripts/evaluate_semantic.py interview` (processes `output/corrected_pali/interview/`)
- Test mode (first 2 chunks only): `uv run python scripts/evaluate_semantic.py -t interview`
- Specific file: `uv run python scripts/evaluate_semantic.py output/corrected_pali/interview/Talk.md`

### Batch Mode

Process multiple files cost-efficiently via OpenAI Batch API:

```bash
# Semantic evaluation only
uv run python scripts/batch.py --stage semantic --folder interview

# With limit (useful for testing)
uv run python scripts/batch.py --stage semantic --folder interview --limit 1

# Submit only, retrieve later
uv run python scripts/batch.py --stage semantic --no-wait
```

Output: Per-file markdown reports in `reports/semantic/<filename>.md` listing all findings.

### Review & Apply Corrections

The ongoing semantic evaluation loop guides you through reviewing findings and applying corrections:

1. Run the evaluator (above)
2. Review each finding interactively (true positive vs. false positive)
3. Apply approved corrections back to `output/corrected_pali/`
4. Re-run evaluator to verify the fixes worked

For details, see: `kamma/threads/ongoing_semantic_evaluation_loop/plan.md`

---

## 5. Dhamma Extraction (Draft)

Extracts core Dhamma points, metadata, and tags from the corrected transcripts.

```bash
PYTHONPATH=. uv run python scripts/extract_dhamma.py <filename>
```

### Environment Setup
Create a `.env` file with your API keys:
```bash
# Google Gemini
GEMINI_API_KEY_1=your_key_here
PROVIDER=google
```

---

## 6. OpenAI Batch Pipeline (Cost-Efficient Alternative)

Run the same Pali correction and Dhamma extraction using the OpenAI Batch API at **50% lower cost** than real-time calls. Batches typically complete within **minutes to hours**. One command orchestrates the full flow: prepare → submit → poll → retrieve.

### When to use this

Use the batch pipeline when you have many files to process and cost matters more than speed. For 1–2 urgent files, use the real-time scripts (`correct_pali.py`, `extract_dhamma.py`) instead. Batches are ideal for processing 10+ files in one go.

### Setup

Add to `.env`:
```
OPENAI_API_KEY=sk-...
OPENAI_PALI_MODEL=gpt-4o-mini      # optional, defaults to gpt-4o-mini
OPENAI_EXTRACT_MODEL=gpt-4o-mini   # optional, defaults to gpt-4o-mini
OPENAI_SEMANTIC_MODEL=gpt-4o-mini  # optional, defaults to gpt-4o-mini
```

### Usage

**Full pipeline** — prepare, submit, auto-poll (every 30s), and retrieve:

```bash
# Both pali + extract (default)
uv run python scripts/batch.py

# Pali correction only
uv run python scripts/batch.py --stage pali

# Extract only
uv run python scripts/batch.py --stage extract

# Semantic evaluation only
uv run python scripts/batch.py --stage semantic

# Limit to first N files (useful for testing)
uv run python scripts/batch.py --stage pali --limit 1

# Specific subfolder
uv run python scripts/batch.py --stage pali --folder interview

# Custom poll interval (default 30 seconds)
uv run python scripts/batch.py --stage extract --poll-interval 40

# Submit only, don't wait for completion
uv run python scripts/batch.py --stage semantic --no-wait
```

**Check status:**

```bash
# Check latest batch for a task
uv run python scripts/batch.py --status pali

# List all tracked jobs
uv run python scripts/batch.py --list
```

### How it works

The script runs the full pipeline in one command:

1. **Prepare** — Scans input directory, skips already-processed files, writes JSONL to `output/batch_input/`.
2. **Submit** — Uploads JSONL, creates OpenAI batch job, saves job ID to `output/batch_jobs.json`.
3. **Poll** — Checks status every N seconds, prints real-time progress.
4. **Retrieve** — When complete, downloads results and writes output files.

Progress output:
```
Stage: pali
[QUEUE] talk1.md
1 already done, 1 to process
Submitting 14 requests...
Creating batch...
Polling every 30s
Ctrl+C to stop and retrieve manually later
[07:27:54] validating — 0/0
[07:28:25] in_progress — 2/14
[07:29:25] completed — 14/14
Downloading results...
  Written: output/corrected_pali/interview/talk1.md
1 files written
```

**If interrupted (Ctrl+C):** Batch keeps running. Resume with `--status` to check, or wait and run again — the script will skip already-processed files.

### Output format

**Pali-corrected files** (`output/corrected_pali/`): JSON arrays of corrections applied to the text.

**Extracted Dhamma points** (`output/extracted/`): Structured Q&A format with Pāli topic tags:
```markdown
## [khandha] [dukkha]
**Q:** What is the relationship between the five khandhas and dukkha?  
**A:** The five khandhas—rūpa, vedanā, saññā, saṅkhāra, and viññāṇa—are the components of personal experience...
```

### Important notes

- **Skip logic:** Files are skipped if output exists, whether from real-time or batch. Safe to re-run.
- **Job tracking:** All batches are recorded in `output/batch_jobs.json` with status and timestamps.
- **Batch window:** OpenAI has a 24h completion window, but batches usually finish within minutes to hours.

---

## Project Structure

- `/audio` - Raw audio files (categorized by subfolders like `sangha/`, `interview/`)
- `/output/transcribed` - Raw Markdown transcripts
- `/output/extracted` - Final extracted Dhamma points (Draft)
- `/scripts` - Core pipeline scripts
- `/kamma` - Project management, thread plans, and quality loop tracking
