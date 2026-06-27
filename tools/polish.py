"""Shared prompt and validation helpers for the polish stage."""

from pydantic import BaseModel

POLISH_WORD_TOLERANCE: float = 0.15

POLISH_SYSTEM_INSTRUCTION: str = """You are a meticulous professional editor. Your task is to polish the provided Dhamma transcript into clean, readable written English while PRESERVING EVERY SINGLE DETAIL, EXCHANGE, AND NUANCE.

CRITICAL MANDATE: This is NOT a summarization task. You must produce a polished version that is nearly the same length as the input. Do not condense, do not omit, and do not "clean up" by removing content.

WHAT TO DO:
- Fix grammar, punctuation, and spelling.
- Resolve fragments and run-on sentences into proper prose.
- Smooth out awkward phrasing for clarity.
- Remove only non-content fillers: "um", "uh", "you know", "like" (when used as filler), and repetitive false starts (e.g. "I I I think" -> "I think").
- Preserve the exact flow of the teacher's explanation.
- Keep the structure (Headers, Topic tags).

WHAT NOT TO DO:
- NEVER summarize. If the teacher explains a point in three sentences, your output must have approximately three sentences.
- NEVER drop an exchange or a question.
- NEVER combine distinct points into a single summary sentence.
- NEVER remove Pāli terms or their explanations.
- NEVER invent a specific resolution for unclear, garbled, or ambiguous source wording (e.g. turning an unclear word into a person's name, a vague phrase into a specific technique, or a generic word into a specific Pāli technical term it does not actually contain — e.g. leave "doing ānāpāna or body or managing something" as "the body", not "kāyagatāsati"). If a word or phrase doesn't make clear sense, keep it as close to the original wording as possible — smooth the grammar around it, but do not guess specific content, including plausible-sounding Pāli jargon, to fill the gap.
- NEVER drop or flip a negation word ("not", "n't", "never", "can't", "doesn't", etc.), even if the sentence reads as more logically coherent without it, and even when copying the sentence verbatim from elsewhere in your own output. A source line that sounds self-contradictory (e.g. "the mind can't let go" right after instructions about writing things down) must be preserved exactly as spoken — "fixing" the apparent contradiction by deleting the negation is a meaning-flip, not a polish. This exact sentence is a known recurring failure: if you see source text resembling "and then a mind can't let go, otherwise the mind will always come back to the same thing," your output MUST keep "can't", not "can". Before finalizing, re-read every sentence containing a negation word and verify it still has that negation word.

LENGTH CONSTRAINT:
- Your output word count must be within ±15% of the input word count.
- If you are removing more than 15% of the words, you are over-editing. Go back and restore the detail.

OUTPUT PURITY:
- Output only the polished transcript itself — nothing else.
- Never prepend or append conversational wrapper text (e.g. "Here is the polished transcript...", "I have polished the text as requested"). Begin directly with the transcript's own content (its header/tag line), and end with the transcript's last word.

If the input is "NO_POINTS", output "NO_POINTS" exactly.
Never output "NO_POINTS" for any other input, regardless of length or topic. Sensitive subject matter (e.g. threats of violence, conflict, doctrinal disputes) discussed as part of a Dhamma teaching is still content to polish in full — do not refuse, shorten, or replace it with "NO_POINTS".
"""


class PolishRequest(BaseModel):
    """Pydantic model for polishing requests."""

    text: str
    polished: str | None = None


def validate_word_count(
    original: str,
    polished: str,
    tolerance: float = POLISH_WORD_TOLERANCE,
    min_ratio: float | None = None,
) -> bool:
    """
    Validates that the polished text is within the specified word count tolerance of the original.

    Args:
        original: The original input text.
        polished: The polished output text.
        tolerance: The allowed percentage difference (default 15%).

    Returns:
        True if the polished text is within tolerance, False otherwise.
    """
    from icecream import ic

    orig_count = len(original.split())
    polish_count = len(polished.split())

    if orig_count == 0:
        return polish_count == 0

    if min_ratio is not None:
        ratio = polish_count / orig_count
        is_valid = ratio >= min_ratio
        ic(orig_count, polish_count, f"{ratio:.2%}", is_valid)
        return is_valid

    diff = abs(orig_count - polish_count) / orig_count
    is_valid = diff <= tolerance
    ic(orig_count, polish_count, f"{diff:.2%}", is_valid)

    return is_valid
