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

## 4. Dhamma Extraction (Draft)

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

## Project Structure

- `/audio` - Raw audio files (categorized by subfolders like `sangha/`, `interview/`)
- `/output/transcribed` - Raw Markdown transcripts
- `/output/extracted` - Final extracted Dhamma points (Draft)
- `/scripts` - Core pipeline scripts
- `/kamma` - Project management, thread plans, and quality loop tracking
