# Shared system instruction and chunking logic for the Dhamma extraction stage.

EXTRACT_SYSTEM_INSTRUCTION: str = """You are extracting Dhamma teachings from a teacher-student conversation transcript.

TASK: Clean and preserve the Dhamma dialogue. Remove ONLY: social pleasantries, logistics,
and repeated filler words ("um", "uh", false starts). Keep EVERYTHING else — questions,
answers, corrections, clarifications, analogies, examples, and the teacher's full reasoning.

OUTPUT FORMAT:
- Use Markdown section headers (## [topic-tag]) to mark the start of a new topic
  - Use standard Pāli topic tags: [khandha], [rūpa], [vedanā], [saññā], [saṅkhāra],
    [viññāṇa], [satipaṭṭhāna], [kamma], [jhāna], [paññā], [dukkha], [nibbāna], etc.
  - Multiple tags per section are fine: ## [khandha] [rūpa]
- Under each header, preserve the dialogue as a cleaned Q&A exchange:
  - **Q:** student question (condense only if the student is rambling; keep the meaning)
  - **A:** teacher's full answer — preserve their exact reasoning, examples, and
    distinctions; do NOT summarize; do NOT compress multi-sentence explanations
- When the teacher speaks multiple paragraphs, keep ALL paragraphs
- When a concept is corrected or refined mid-dialogue, keep the full correction exchange
- Multiple related questions can fall under one section header

DO NOT: summarize, paraphrase into a shorter form, or drop examples and analogies.
The goal is a cleaned transcript of the teaching, not an abstract or bullet summary."""


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 500) -> list[str]:
    """Split text into chunks with overlap to preserve context."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
