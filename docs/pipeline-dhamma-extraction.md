# Dhamma Extraction Pipeline

Covers the three post-transcription stages: Pāli spelling correction, Dhamma point extraction, and prose polishing.

---

```bash
./extract_run.sh
```

---

## 1. Pali Spelling Correction

Refines Pāli term spelling in transcripts using a consolidated glossary of ~155 terms.

**Process all transcripts:**
```bash
uv run python scripts/correct_pali.py
```

**Process a specific file or folder:**
```bash
uv run python scripts/correct_pali.py <filename_or_path>
```

Output: `output/corrected_pali/`, mirroring the input directory structure.

---

## 2. Dhamma Extraction

Extracts core Dhamma points, metadata, and tags from corrected transcripts.

```bash
uv run python scripts/extract_dhamma.py <filename>
```

Output: `output/extracted/`

---

## 3. Polishing

Rewrites extraction output into clean, readable English prose. Fixes fragmented sentences and non-native patterns while preserving all teaching points.

```bash
uv run python scripts/polish_extract.py output/extracted/interview/Talk.md
```

**Options:**
- `--dry-run`: see the prompt and input without calling the API
- `--output-dir <path>`: override default `output/polished/` destination

Output: `output/polished/`
