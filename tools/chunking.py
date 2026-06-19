"""Shared paragraph-preserving text chunking helpers."""


def chunk_text_by_paragraph(text: str, chunk_size: int = 2000) -> list[str]:
    """Split text into word-limited chunks on blank-line paragraph boundaries."""
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
