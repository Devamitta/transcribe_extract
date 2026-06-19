"""Regression tests for tag-grouped Dhamma database consolidation."""

from pathlib import Path

from scripts import consolidate


def test_consolidate_groups_tags_prefers_polished_and_includes_fallback(
    tmp_path: Path,
) -> None:
    polished = tmp_path / "output" / "polished"
    extracted = tmp_path / "output" / "extracted"
    polished_file = polished / "interview" / "talk.md"
    extracted_shadow = extracted / "interview" / "talk.md"
    extracted_only = extracted / "sangha" / "only.md"
    untagged_file = polished / "plain.md"
    polished_file.parent.mkdir(parents=True)
    extracted_shadow.parent.mkdir(parents=True)
    extracted_only.parent.mkdir(parents=True)
    polished_file.write_text(
        "Intro before tags.\n\n"
        "## [jhāna]\n"
        "Polished jhāna section.\n\n"
        "## [mettā]\n"
        "Polished mettā section.",
        encoding="utf-8",
    )
    extracted_shadow.write_text(
        "## [jhāna]\nExtracted shadow should not appear.",
        encoding="utf-8",
    )
    extracted_only.write_text(
        "## [jhāna]\nExtracted-only jhāna section.",
        encoding="utf-8",
    )
    untagged_file.write_text("No tag here.", encoding="utf-8")

    output_path = tmp_path / "master.md"
    result = consolidate.consolidate(
        polished_dir=polished,
        extracted_dir=extracted,
        output_path=output_path,
    )
    output = output_path.read_text(encoding="utf-8")

    assert result.source_count == 3
    assert result.tagged_count == 3
    assert result.untagged_count == 2
    assert "## [jhāna]" in output
    assert "## [mettā]" in output
    assert "### Source: interview/talk.md" in output
    assert "### Source: sangha/only.md" in output
    assert "Polished jhāna section." in output
    assert "Extracted-only jhāna section." in output
    assert "Extracted shadow should not appear." not in output
    assert "## Untagged Sources" in output
    assert "Intro before tags." in output
    assert "No tag here." in output
