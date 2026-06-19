"""Tests YouTube cover title line splitting behavior."""

from scripts.yt_cover_gen import _split_title_segments


def test_split_title_segments_breaks_common_title_separators() -> None:
    title = (
        "Knowing Dukkha: Letting Go | Practice/Q&A; Reflection • Review, Resolve. End"
    )

    assert _split_title_segments(title) == [
        "Knowing Dukkha",
        "Letting Go",
        "Practice",
        "Q&A",
        "Reflection",
        "Review, Resolve",
        "End",
    ]


def test_split_title_segments_keeps_hyphenated_words() -> None:
    title = "Non-self Practice - Direct Seeing"

    assert _split_title_segments(title) == [
        "Non-self Practice",
        "Direct Seeing",
    ]
