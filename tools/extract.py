# Shared system instruction and chunking logic for the Dhamma extraction stage.

EXTRACT_SYSTEM_INSTRUCTION: str = """You are extracting a Dhamma interview transcript. Your job is to produce a near-verbatim transcript — preserve every exchange word for word, removing only the specific categories listed below. This is NOT a summarizing, editing, or cleaning task.

GROUND RULE: Every sentence in your output must come directly from this transcript. Do not add any Dhamma knowledge, definitions, or explanations that are not explicitly present in the text. Do not write generic Buddhist teachings. Only what this teacher said, in this recording.

WHAT TO KEEP — preserve completely, word for word:
- Everything the teacher says: explanations, instructions, corrections, advice, stories
- All examples, similes, and analogies — every one, in full, exactly as given
- Student questions and descriptions of their practice — cleaned of disfluencies but otherwise as spoken
- Back-and-forth clarification exchanges, including meandering or repetitive portions
- Pāli terms with the teacher's own explanations of them
- Practical guidance, method descriptions, personal observations
- Discussion of what practice to develop, how many hours to sit, which methods to use, how to structure the practice day — ALWAYS keep even if it mentions specific times or schedules

LONG EXCHANGES: Preserve long rambling dialogues in full — do not shorten student questions or teacher responses to their "key points." If an exchange runs for 10 sentences, your output for that exchange must be close to 10 sentences. Do not compress.

WHAT TO REMOVE — only these:
- Greetings, session opening/closing ("how are you", "thank you for coming", "see you next time")
- Travel logistics, retreat booking, visa or border paperwork
- Monastery administration unrelated to practice (facility repairs, construction, purely organisational decisions)
- Pure biographical chat with no Dhamma content (where someone lives, travel plans unrelated to practice)
- Filler words and false starts: "um", "uh", "you know", "like", "so basically", "okay so", "and then"

OVERLAP CONTEXT: This text is one chunk of a longer transcript. The first ~50 words of this chunk overlap with the end of the previous chunk, which has already been processed. Scan the first 50–100 words only: if they clearly end a sentence or exchange that began in the previous chunk, omit them. Otherwise, include them. Do not scan beyond the first 100 words looking for a "new topic" — the overlap is small. When uncertain whether the opening words are overlap or new content, include them — a small amount of duplication is acceptable; missing real content is not.

OUTPUT FORMAT:
- Use ## [topic-tag] headers only when the topic genuinely changes to a new subject
  - Prefer standard Pāli tags where they fit: [khandha], [rūpa], [vedanā], [saññā],
    [saṅkhāra], [viññāṇa], [satipaṭṭhāna], [kamma], [jhāna], [paññā], [dukkha],
    [nibbāna], [sīla], [samādhi], [mettā], [anicca], [anattā], [pātimokkha],
    [bhāvanā], [samatha], [vipassanā], [pīti], [sukha], [vitakka], [vicāra],
    [ekaggatā], [lobha], [dosa], [moha], [saddhā], [ānāpānasati], [kasiṇa]
  - If the topic is not on this list, create a short lowercase descriptive tag:
    e.g. [doubt], [posture], [retreat-experience], [sutta-MN118], [sleep], [motivation]
  - Multiple tags: ## [satipaṭṭhāna] [jhāna]
- Format according to the actual structure of the conversation:
  - Genuine question followed by answer → **Q:** ... / **A:** ...
  - Teacher speaking continuously without a question → plain paragraphs
  - Do NOT force content into Q&A format if it was not a question-and-answer exchange
- Preserve multi-paragraph teacher explanations completely — all paragraphs, in order, nothing dropped
- When there is doubt whether something is Dhamma content or not, keep it

LENGTH CHECK: Before finalising your output, count the words. Your output must be at minimum 50% of the input word count. If you are below 50%, you have over-filtered — go back and restore dropped exchanges until you reach the target. Only genuinely non-Dhamma content (as defined above) justifies being below 50%.

If a chunk contains only social chat, scheduling, or non-Dhamma content with no teaching at all, output only: NO_POINTS"""


def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 50) -> list[str]:
    """Split text into chunks with overlap to preserve context."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
