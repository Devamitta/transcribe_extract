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

Status: **Active - Monitoring New Transcripts**
- Iterative loop for analyzing manual transcriptions and improving automated filters.
- Uses existing infrastructure tools to detect anomalies and generate diff reports.
- Proposes filter/script improvements based on AI analysis of recurring errors.

