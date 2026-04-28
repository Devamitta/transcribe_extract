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
- Keep the structure (Headers, Q&A format, Topic tags).

WHAT NOT TO DO:
- NEVER summarize. If the teacher explains a point in three sentences, your output must have approximately three sentences.
- NEVER drop an exchange or a question.
- NEVER combine distinct points into a single summary sentence.
- NEVER remove Pāli terms or their explanations.

LENGTH CONSTRAINT:
- Your output word count must be within ±15% of the input word count.
- If you are removing more than 15% of the words, you are over-editing. Go back and restore the detail.

If the input is "NO_POINTS", output "NO_POINTS" exactly.
"""


class PolishRequest(BaseModel):
    """Pydantic model for polishing requests."""

    text: str
    polished: str | None = None


def validate_word_count(
    original: str,
    polished: str,
    tolerance: float = POLISH_WORD_TOLERANCE,
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

    diff = abs(orig_count - polish_count) / orig_count
    is_valid = diff <= tolerance

    ic(orig_count, polish_count, f"{diff:.2%}", is_valid)

    return is_valid
