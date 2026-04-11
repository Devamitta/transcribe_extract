# Project Threads

This file lists all major threads for the project. Each thread has its own detailed plan in its respective folder.

---

## [~] Thread: Improve Extraction Prompt (reduce summarization)
*Link: [./kamma/threads/20250408_improve_extraction_prompt/](./kamma/threads/20250408_improve_extraction_prompt/)*

Status: **Awaiting user review**
- Rewrite SYSTEM_INSTRUCTION in scripts/extract_dhamma.py
- Switch from bulleted list to cleaned Q&A dialogue format
- Preserve teacher's full explanations, examples, student questions
- Word count improved: test_3500 4x, test_another similar
- Awaiting user approval to stage


---

## [~] Thread: Process Tims audio recordings with folder-aware transcription, upload-title and YouTube upload-description suggestions, and reviewed export packaging
*Link: [./kamma/threads/20260408_tims_audio_pipeline/](./kamma/threads/20260408_tims_audio_pipeline/)*


---

## [~] Thread: Ongoing Transcription Quality Feedback Loop
*Link: [./kamma/threads/ongoing_transcription_feedback/](./kamma/threads/ongoing_transcription_feedback/)*

Status: **In Progress - Iteration 3: Refined Error Reporting & Hallucination Filter**
- Resolved "poisoned context" bug in scripts/transcribe.py causing silent truncation of long files.
- **New Fix (2026-04-11)**: Updated `scripts/extract_errors.py` with a tiered repetition check to eliminate false positives from natural speech stutters.
- **Improved Filter**: Enhanced Phrase Loop Filter in `scripts/transcribe.py` to catch punctuation-agnostic repetitions (e.g. "It's possible. It's possible.").
- **Latest Finding**: Verified transcription quality of recent Saṅgha meetings; current real anomaly count reduced to 1 (detected correctly as a triple repetition loop).
- **Awaiting User Review**: Confirming if the refined error report accurately reflects the current state of transcription quality.

