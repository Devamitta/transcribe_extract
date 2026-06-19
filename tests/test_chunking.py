"""Regression tests for paragraph-preserving chunking helpers."""

from tools.chunking import chunk_text_by_paragraph
from tools.pali import chunk_text_no_overlap


def legacy_chunk_text_no_overlap(text: str, chunk_size: int = 2000) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0
    for paragraph in paragraphs:
        words = len(paragraph.split())
        if current_length + words > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(paragraph)
        current_length += words
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    return chunks


def test_paragraph_chunker_preserves_markdown_headers_and_line_breaks() -> None:
    text = "## [jhāna]\nLine one\nLine two\n\n**Q:** What is this?\n**A:** A preserved block."

    chunks = chunk_text_by_paragraph(text, chunk_size=20)

    assert chunks == [text]


def test_paragraph_chunker_respects_size_limit_at_paragraph_boundaries() -> None:
    first = " ".join(f"a{i}" for i in range(6))
    second = " ".join(f"b{i}" for i in range(5))
    third = " ".join(f"c{i}" for i in range(4))

    chunks = chunk_text_by_paragraph(f"{first}\n\n{second}\n\n{third}", chunk_size=10)

    assert chunks == [first, f"{second}\n\n{third}"]


def test_paragraph_chunker_passes_through_oversized_single_paragraph() -> None:
    oversized = " ".join(f"w{i}" for i in range(12))

    chunks = chunk_text_by_paragraph(oversized, chunk_size=5)

    assert chunks == [oversized]


def test_pali_reexport_matches_legacy_chunker_output() -> None:
    fixture = "alpha beta\n\n## [tag]\ngamma delta\n\n\n\nepsilon zeta eta\n\ntheta"

    assert chunk_text_no_overlap(fixture, chunk_size=4) == legacy_chunk_text_no_overlap(
        fixture,
        chunk_size=4,
    )
