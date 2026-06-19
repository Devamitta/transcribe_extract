"""Regression tests for the polish pipeline helpers and configuration."""

import hashlib
import json
import unittest
from pathlib import Path

import pytest

from scripts import batch, polish_extract
from tools import extract, polish
from tools.chunk_runner import EXIT_OK, EXIT_PARTIAL
from tools.incremental import get_temp_path


class PolishPipelineTests(unittest.TestCase):
    """Covers thread-specific polish behavior and wiring."""

    def test_batch_polish_chunking_avoids_overlap_duplication(self) -> None:
        text = " ".join(f"w{i}" for i in range(6100))

        chunks = batch.TASK_CONFIG["polish"]["chunk_fn"](text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[1].startswith("w3000 "))

    def test_batch_extract_prompt_keeps_previous_full_prompt(self) -> None:
        full_prompt = extract.EXTRACT_SYSTEM_INSTRUCTION_WITH_OVERLAP

        self.assertNotIn("OVERLAP CONTEXT:", extract.EXTRACT_SYSTEM_INSTRUCTION)
        self.assertIn("OVERLAP CONTEXT:", extract.EXTRACT_OVERLAP_CONTEXT)
        self.assertEqual(
            batch.TASK_CONFIG["extract"]["get_instruction"](Path("sample.md")),
            full_prompt,
        )
        self.assertEqual(
            hashlib.sha256(full_prompt.encode()).hexdigest(),
            "d9ae3339107e8783482faa55766f95a875517ec0b4a1bd91743213405f5a83ea",
        )

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

    def test_validate_word_count_min_ratio_mode_allows_long_output(self) -> None:
        original = " ".join(["word"] * 100)
        polished_text = " ".join(["word"] * 200)

        self.assertTrue(
            polish.validate_word_count(original, polished_text, min_ratio=0.5),
        )

    def test_validate_word_count_min_ratio_mode_rejects_short_output(self) -> None:
        original = " ".join(["word"] * 100)
        polished_text = " ".join(["word"] * 49)

        self.assertFalse(
            polish.validate_word_count(original, polished_text, min_ratio=0.5),
        )

    def test_validate_word_count_min_ratio_empty_original_matches_default(self) -> None:
        self.assertTrue(polish.validate_word_count("", "", min_ratio=0.5))
        self.assertFalse(polish.validate_word_count("", "word", min_ratio=0.5))

    def test_is_no_points_normalizes_wrapped_variants(self) -> None:
        self.assertTrue(extract.is_no_points("NO_POINTS"))
        self.assertTrue(extract.is_no_points("NO_POINTS."))
        self.assertTrue(extract.is_no_points("  no_points\n"))
        self.assertTrue(extract.is_no_points("Result:\nNO_POINTS\n"))
        self.assertFalse(extract.is_no_points("This chunk contains teaching points."))


def test_polish_chunk_validation_failure_retries_then_keeps_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_file = tmp_path / "output" / "extracted" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text(
        "one two three four five six seven eight nine ten", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    def polish_too_short(_text: str, _file_path: Path | None = None) -> str:
        return "short"

    monkeypatch.setattr(polish_extract, "polish_text", polish_too_short)
    monkeypatch.setattr(polish_extract, "INTER_CALL_PACING_SECONDS", 0)

    exit_code = polish_extract.main([])
    output_file = tmp_path / "output" / "polished" / "talk.md"
    temp_file = get_temp_path(output_file)

    assert exit_code == EXIT_PARTIAL
    assert not output_file.exists()
    assert json.loads(temp_file.read_text(encoding="utf-8")) == [None]


def test_polish_dry_run_lists_queue_without_provider_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_file = tmp_path / "output" / "extracted" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("content", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def fail_if_called(_text: str, _file_path: Path | None = None) -> str:
        raise AssertionError("provider should not be called during dry-run")

    monkeypatch.setattr(polish_extract, "polish_text", fail_if_called)

    exit_code = polish_extract.main(["--dry-run"])
    captured = capsys.readouterr()

    assert exit_code == EXIT_OK
    assert "output/extracted/talk.md" in captured.out
    assert not (tmp_path / "output" / "polished" / "talk.md").exists()


def test_polish_whole_file_val_fail_path_removed() -> None:
    source = Path(polish_extract.__file__).read_text(encoding="utf-8")

    assert "[VAL FAIL]" not in source


if __name__ == "__main__":
    unittest.main()
