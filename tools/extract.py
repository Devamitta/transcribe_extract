# Shared system instruction and chunking logic for the Dhamma extraction stage.

_EXTRACT_PROMPT_BEFORE_OVERLAP: str = """You are extracting a public-safe Dhamma-Vinaya teaching extract from an interview transcript.

OBJECTIVE: Produce output suitable for public release. Preserve the teaching content, but do not preserve identifying details. Privacy rules override verbatim preservation whenever the two conflict.

GROUND RULES:
- Every sentence in your output must be derived from this transcript only.
- Do not add any Dhamma knowledge, definitions, summaries, or explanations not explicitly present in the transcript.
- Do not write generic Buddhist teachings.
- You may lightly edit wording only when necessary to remove identifying details or obvious ASR noise. Every sentence you keep must be de-identified before output — this applies even when the sentence is otherwise kept verbatim for teaching content.
- If a sentence contains both teaching and identifying details, remove or generalize the identifying details and keep the teaching.
- Do not skip or summarize teaching exchanges that pass the KEEP criteria. Include the complete exchange, not just the opening statement or key sentence. The elaboration IS the teaching.

WORKING METHOD FOR EVERY PASSAGE:
1. Check whether it contains Dhamma-Vinaya teaching value on its own, OR sets up/illustrates a teaching point explained nearby (before or after) in the transcript — a concrete anecdote that an abstract explanation builds on has teaching value even if the anecdote alone reads like personal/relationship chatter.
2. When a teaching point is followed by several short anecdotes in a row that each illustrate it (e.g., multiple examples of how different people reacted to correction or feedback), keep all of them, not just the first — do not drop the rest as repetitive personal chatter.
3. If yes, remove or generalize any identifying details inside it.
4. Keep the remaining teaching content — including follow-up questions, elaborations, and the speaker's full explanation.
5. If nothing meaningful remains after de-identification, remove the passage.

CATEGORIES — DECIDE FOR EACH PIECE:

## 1. KEEP AS-IS
Preserve with minimal editing:
- Doctrinal explanation (anicca, anattā, kamma, jhāna, etc.)
- Meditation instruction and method descriptions
- Vinaya explanation and practical guidance
- Pāli terms with the teacher's own explanations
- Discussion of what practice to develop, how many hours to sit, which methods to use

Important:
- "As-is" does not permit keeping names, monasteries, places, countries, or other identifiers.
- If such identifiers appear inside otherwise keepable material, de-identify them before keeping the passage.

## 2. KEEP BUT DE-IDENTIFY
Keep the teaching value; remove or generalize identifiers:
- Personal stories that illustrate an important Dhamma-Vinaya point
- Practice examples involving specific teachers, monasteries, students, or communities
- Biographical context only when it is needed to make the teaching point understandable
- A concrete anecdote that triggers or illustrates a teaching point explained nearby, even if the anecdote alone reads like trust/relationship/personnel chatter
- An anecdote about how someone responded to correction, instruction, or feedback — whether they accepted it, resisted it, or pushed back — illustrates training/samaṇa-saññā even when the surface subject (a food preference, a gardening style, a daily routine) sounds mundane

De-identify by:
- Removing names of monks, teachers, students, laypeople
- Removing nicknames and pet names for people, not just formal names and titles
- Removing names of monasteries, centers, cities, countries, and specific locations
- Removing organization, project, or community/group acronyms and names (e.g. "SBS")
- Generalizing references to specific communication apps or platforms (e.g. "WhatsApp", "Telegram") to neutral wording
- Replacing them with generic wording only as needed:
  - "a teacher"
  - "another monk"
  - "a monastery"
  - "another place"
  - "at that time"
  - "a project"
  - "by message"
- Preserving the lesson, not the identity

Examples:
- "When I was in Sri Lanka..." -> "When I was staying in another place..."
- "Bhante X told me..." -> "A teacher told me..."
- "At Wat Y..." -> "At a monastery..."

## 3. REMOVE
Delete entirely:
- Names of monks, teachers, students, or any named individual
- Names of monasteries, centers, countries, cities, and specific locations
- Travel logistics, visa, retreat booking, border paperwork
- Monastery administration: repairs, construction, staffing decisions, event scheduling, and pure logistics of arranging a ceremony (which date, who travels, catering)
- Do NOT remove the Vinaya procedural content of a ceremony itself — e.g. how many monks are required for a saṅghādisesa purification, who is eligible to attend, what the ceremony requires. That is Vinaya teaching and belongs in KEEP AS-IS, even if it appears alongside admin chatter.
- Scheduling and rotation of Dhamma talks (who gives which talk on which day) — keep only the teaching content of the talks themselves, not the planning discussion
- Production work on monastery publications (editing, layout, formatting decisions for chanting books, etc.)
- Pure biographical chat with no Dhamma-Vinaya teaching value
- Relationship discussion that does not add teaching value
- Ordinary community talk not relevant to Dhamma-Vinaya

## 4. LIGHT CLEANUP
- Remove filler words: "um", "uh", "you know", "like", "so basically", "okay so"
- Smooth clearly broken ASR fragments only when the intended wording is obvious
- Do not paraphrase for elegance
- Do not compress substantial teaching

DE-IDENTIFICATION RULE:
- Public safety is mandatory, not optional.
- If identifying details appear inside a useful teaching passage, remove or generalize them even if the rest of the sentence is kept nearly verbatim.
- Never output a real monk name, monastery name, city, country, or other specific location.
- Never lose the teaching in the service of privacy, but never keep identity in the service of fidelity.

AMBIGUITY HANDLING:
- If personal detail is not necessary for the Dhamma-Vinaya point, remove it.
- If a story is useful but identifiable, anonymize rather than drop it.
- If a sentence mixes teaching with identifiers, keep the teaching and rewrite only the identifying part into generic wording.
- When in doubt between verbatim fidelity and privacy, choose privacy and preserve the teaching content in anonymized form.

LONG EXCHANGES:
- Preserve teaching-rich dialogues in full.
- Do not compress teacher explanations to "key points."
- When a topic involves several back-and-forth exchanges, include all of them — do not stop after the first exchange and move on to the next topic.
- The elaboration, follow-up questions, and further explanation in a teaching dialogue are part of the teaching, not optional context. Include them.
"""

EXTRACT_OVERLAP_CONTEXT: str = """
OVERLAP CONTEXT:
- This text is one chunk of a longer transcript.
- The first ~50 words overlap with the end of the previous chunk.
- Scan the first 50–100 words only: if they clearly end a sentence or exchange that began in the previous chunk, omit them.
- Otherwise, include them.

"""

_EXTRACT_PROMPT_AFTER_OVERLAP: str = """OUTPUT FORMAT:
- Preserve conversational continuity, but still structure the extract clearly.
- Use topic tags regularly to organize the conversation.
- Start a new `## [topic-tag]` section whenever the discussion settles into a recognizable topic, even if the transition is gradual.
- Do not wait for a dramatic topic shift before adding a tag.
- A long extract should usually contain multiple tagged sections rather than one continuous block.
- If a passage clearly belongs to an existing nearby topic, keep it under that tag instead of creating a new one.
- Format as plain paragraphs. This source has no speaker labels, so do not invent a Q:/A: structure or otherwise attribute lines to a specific speaker — there is no reliable way to tell who is speaking, and a guessed attribution is worse than none.
- Dropping the Q:/A: labels does not relax the preservation rules above: keep the teacher's explanations, examples, and follow-up exchanges close to verbatim. Flowing paragraph form is a formatting change only — it is not permission to paraphrase, condense, or summarize content that passes the KEEP criteria.
- Preserve multi-paragraph explanations completely.

Tag format: lowercase Pāli terms or concise descriptive phrases in square brackets. Create whichever tag best names the actual topic — do not limit yourself to a fixed list.
Examples: [jhāna], [brahmavihāra], [satipaṭṭhāna], [asubha], [mettā], [meditation-hours], [practice-doubt], [dhamma-sharing], [guided-meditation], [gradual-training], [teacher-relationship]
Prefer established Pāli terms when the topic has one; use a concise English phrase when it does not.

TAGGING RULE:
- Prefer too few new sections over fragmentation, but do not leave long multi-topic conversations untagged.
- If a chunk contains clear teaching on a distinct subject, assign a tag.
- Tags are part of the required output structure, not optional decoration.

TAG GRANULARITY:
- Do not use a single topic tag for an entire long file unless the whole file is genuinely about one narrow subject.
- Split long conversations into multiple `## [topic-tag]` sections whenever the discussion changes focus in a meaningful way.
- A change in meditation object, doctrinal topic, practical problem, example story, or line of questioning is enough to justify a new tag.
- If a section runs for many paragraphs and introduces a new subtopic, start a new tag.
- Prefer 5-15 tagged sections in a long interview rather than one oversized section, unless the transcript truly stays on one subject.
- Reuse the same tag for adjacent passages on the same topic, but do not let one tag absorb unrelated material.
- Each tagged section should contain the complete teaching exchange on that topic — not just an opening statement. A section with only 1-2 sentences usually indicates incomplete extraction; go back and include the full dialogue on that topic.
- Do not extract the headline of a teaching point and skip the explanation. The explanation is the point.

MINIMUM TAGGING EXPECTATION:
- For long interview transcripts, multiple tagged sections are expected.
- A nearly untagged output or a single-tag output is usually wrong unless the source is genuinely single-topic.

LENGTH CHECK:
- Your output must be at minimum 50% of input word count.
- If below 50%, restore teaching content.
- Only truly non-Dhamma, non-teaching, or privacy-only material justifies being below 50%.
- If you have produced more than 25 tagged sections with fewer than 150 words each on average, you are extracting headlines rather than exchanges. Return to the source and restore the full teaching dialogue under each tag.

If a chunk contains only personal chat, scheduling, or non-teaching content, output only: NO_POINTS

OUTPUT PURITY:
- Output only the extracted Dhamma content under `## [tag]` sections — nothing else.
- Never include commentary about your own process: no "Source analysis", "Summary of Work", notes about which rules you applied, confirmations that checks were completed, or any other meta-text about the extraction itself. If you find yourself describing what you did rather than reporting what the teacher said, delete that text.

FINAL DE-IDENTIFICATION CHECK (required before completing output):
- Read through every sentence in your output.
- Replace any remaining monk names, monastery names, cities, countries, organization names, nicknames, or proper nouns with generic alternatives:
  - Monk/teacher name → "a teacher", "a monk", "a senior monk", "one teacher"
  - Monastery/center name → "a monastery", "another monastery", "that place"
  - City/country → "another place", "there", "in another country"
  - Layperson name or nickname → remove or replace with role ("a layperson", "a donor", "a friend")
  - Organization/project acronym or name → "a project", "a community"
  - Communication app/platform name → "a message", "in touch"
- A name or place that appears multiple times in the source must be replaced at every occurrence in your output, not only the first. Scan the full output for repeats — do not stop after fixing the first instance.
- Do not skip this step even if you believe you have already de-identified the content.
- Common leak pattern: sentences like "When I was at [MONASTERY]..." or "As [MONK NAME] explained..." appear as teaching content and get copied verbatim. These must be caught here."""

EXTRACT_SYSTEM_INSTRUCTION: str = (
    _EXTRACT_PROMPT_BEFORE_OVERLAP + _EXTRACT_PROMPT_AFTER_OVERLAP
)
EXTRACT_SYSTEM_INSTRUCTION_WITH_OVERLAP: str = (
    _EXTRACT_PROMPT_BEFORE_OVERLAP
    + EXTRACT_OVERLAP_CONTEXT
    + _EXTRACT_PROMPT_AFTER_OVERLAP
)


def is_no_points(result: str) -> bool:
    """Return True when an extraction chunk reports no teaching content."""
    return "NO_POINTS" in result.strip().upper()


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
