"""Verifies provider-backed prompts start with a stable cache-friendly prefix."""

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import (
    correct_pali,
    evaluate_semantic,
    extract_dhamma,
    polish_extract,
    yt_metadata,
)
from tools.provider import CACHE_PREFIX, build_cacheable_contents


class ProviderCachePromptTests(unittest.TestCase):
    """Covers cache-friendly request formatting for provider callers."""

    def test_build_cacheable_contents_prefixes_unique_text(self) -> None:
        unique_text = "unique request payload"

        contents = build_cacheable_contents(unique_text)

        self.assertEqual(contents, f"{CACHE_PREFIX}{unique_text}")

    def test_extract_dhamma_points_sends_cacheable_contents(self) -> None:
        text = "extract me"

        with patch(
            "scripts.extract_dhamma.generate_content", return_value="ok"
        ) as mock_call:
            extract_dhamma.extract_dhamma_points(text)

        self.assertEqual(
            mock_call.call_args.kwargs["contents"], f"{CACHE_PREFIX}{text}"
        )

    def test_polish_text_sends_cacheable_contents(self) -> None:
        text = "polish me"

        with patch(
            "scripts.polish_extract.generate_content", return_value="ok"
        ) as mock_call:
            polish_extract.polish_text(text)

        self.assertEqual(
            mock_call.call_args.kwargs["contents"], f"{CACHE_PREFIX}{text}"
        )

    def test_evaluate_chunk_sends_cacheable_contents(self) -> None:
        text = "semantic chunk"

        with patch(
            "scripts.evaluate_semantic.generate_content", return_value="[]"
        ) as mock_call:
            evaluate_semantic.evaluate_chunk(text)

        self.assertEqual(
            mock_call.call_args.kwargs["contents"], f"{CACHE_PREFIX}{text}"
        )

    def test_correct_pali_transcription_sends_cacheable_contents(self) -> None:
        text = "pali chunk"

        with patch(
            "scripts.correct_pali.generate_content", return_value="[]"
        ) as mock_call:
            correct_pali.correct_pali_transcription(text, Path("talk.md"))

        self.assertEqual(
            mock_call.call_args.kwargs["contents"], f"{CACHE_PREFIX}{text}"
        )

    def test_generate_metadata_sends_cacheable_contents(self) -> None:
        text = "metadata body"

        with patch(
            "scripts.yt_metadata.generate_content", return_value="ok"
        ) as mock_call:
            yt_metadata.generate_metadata(text, "en")

        self.assertEqual(
            mock_call.call_args.kwargs["contents"], f"{CACHE_PREFIX}{text}"
        )


if __name__ == "__main__":
    unittest.main()
