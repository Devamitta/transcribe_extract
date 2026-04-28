"""Regression tests for the polish pipeline helpers and configuration."""

import unittest
from pathlib import Path

from scripts import batch, polish_extract
from tools import polish


class PolishPipelineTests(unittest.TestCase):
    """Covers thread-specific polish behavior and wiring."""

    def test_batch_polish_chunking_avoids_overlap_duplication(self) -> None:
        text = " ".join(f"w{i}" for i in range(6100))

        chunks = batch.TASK_CONFIG["polish"]["chunk_fn"](text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[1].startswith("w3000 "))

    def test_build_parser_supports_dry_run(self) -> None:
        parser = polish_extract.build_parser()

        args = parser.parse_args(["--dry-run"])

        self.assertTrue(args.dry_run)

    def test_mirror_path_preserves_relative_directories(self) -> None:
        output_path = polish_extract.mirror_path(
            Path("output/extracted/interview/example.md"),
            Path("output/extracted"),
            Path("output/polished"),
        )

        self.assertEqual(output_path, Path("output/polished/interview/example.md"))

    def test_resolve_stages_includes_polish_for_both(self) -> None:
        self.assertEqual(batch.resolve_stages("both"), ["pali", "extract", "polish"])

    def test_validate_word_count_rejects_more_than_fifteen_percent_drift(self) -> None:
        original = " ".join(["word"] * 100)
        polished_text = " ".join(["word"] * 116)

        self.assertFalse(polish.validate_word_count(original, polished_text))


if __name__ == "__main__":
    unittest.main()
