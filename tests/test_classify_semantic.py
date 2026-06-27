"""Tests for semantic classification module."""

from pathlib import Path

import pytest

from tools.semantic_classify import (
    ClassificationError,
    build_classification_instruction,
    classify_findings,
    enforce_single_word_rule,
    format_compact,
    is_multi_word_correction,
    load_carried_patterns,
    parse_report,
)


REPORT_FIXTURE = """# Semantic Evaluation: talk

## Passage
> Bhatimokha is recited

**Context:** We gather for the Bhatimokha every fortnight.

**Issue:** Whisper garbled Patimokkha

**Suggestion:** 'Bhatimokha' -> 'Pāṭimokkha'

---

## Passage
> the nature of anicca

**Context:** He explained the nature of anicca and dukkha.

**Issue:** Could 'a nature' be a garble?

**Suggestion:** 'a nature' -> 'anicca'

---

## Passage
> the the eye

**Context:** We see with the the eye and ear.

**Issue:** Duplicate word error

**Suggestion:** 'the the' -> 'the'

---"""


def test_parse_report(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text(REPORT_FIXTURE, encoding="utf-8")

    findings = parse_report(path)

    assert len(findings) == 3
    assert findings[0]["passage"] == "Bhatimokha is recited"
    assert "Pāṭimokkha" in findings[0]["suggestion"]
    assert findings[1]["passage"] == "the nature of anicca"
    assert "a nature" in findings[1]["suggestion"]
    assert findings[2]["passage"] == "the the eye"


def test_parse_report_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text(
        "# Semantic Evaluation: empty\n\n_No anomalies detected._\n", encoding="utf-8"
    )
    findings = parse_report(path)
    assert len(findings) == 0


def test_classify_findings_success(monkeypatch: pytest.MonkeyPatch) -> None:
    findings = [
        {
            "passage": "Bhatimokha",
            "context": "reciting the Bhatimokha",
            "issue": "garbled",
            "suggestion": "Pāṭimokkha",
        },
    ]
    response = '[{"passage": "Bhatimokha", "classification": "TP-fix", "reason": "single word phonetic match"}]'

    monkeypatch.setattr(
        "tools.semantic_classify.generate_with_timeout",
        lambda **kwargs: response,
    )

    instruction = build_classification_instruction("", "")
    result = classify_findings(findings, instruction)

    assert len(result) == 1
    assert result[0]["classification"] == "TP-fix"
    assert "Bhatimokha" in result[0]["passage"]


def test_classify_findings_strips_json_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    findings = [
        {"passage": "x", "context": "", "issue": "", "suggestion": ""},
    ]
    response = '```json\n[{"passage": "x", "classification": "FP", "reason": "nothing wrong"}]\n```'

    monkeypatch.setattr(
        "tools.semantic_classify.generate_with_timeout",
        lambda **kwargs: response,
    )

    instruction = build_classification_instruction("", "")
    result = classify_findings(findings, instruction)

    assert result[0]["classification"] == "FP"


def test_classify_findings_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    findings = [
        {"passage": "x", "context": "", "issue": "", "suggestion": ""},
    ]

    monkeypatch.setattr(
        "tools.semantic_classify.generate_with_timeout",
        lambda **kwargs: "",
    )

    instruction = build_classification_instruction("", "")
    with pytest.raises(ClassificationError, match="empty response"):
        classify_findings(findings, instruction)


def test_classify_findings_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    findings = [
        {"passage": "x", "context": "", "issue": "", "suggestion": ""},
    ]

    monkeypatch.setattr(
        "tools.semantic_classify.generate_with_timeout",
        lambda **kwargs: "not json",
    )

    instruction = build_classification_instruction("", "")
    with pytest.raises(ClassificationError, match="invalid JSON"):
        classify_findings(findings, instruction)


def test_classify_findings_non_list_json(monkeypatch: pytest.MonkeyPatch) -> None:
    findings = [
        {"passage": "x", "context": "", "issue": "", "suggestion": ""},
    ]

    monkeypatch.setattr(
        "tools.semantic_classify.generate_with_timeout",
        lambda **kwargs: '{"key": "value"}',
    )

    instruction = build_classification_instruction("", "")
    with pytest.raises(ClassificationError, match="not a list"):
        classify_findings(findings, instruction)


def test_classify_findings_empty_input() -> None:
    instruction = build_classification_instruction("", "")
    result = classify_findings([], instruction)
    assert result == []


def test_is_multi_word_correction_single_word() -> None:
    assert is_multi_word_correction("'Bhatimokha' -> 'Pāṭimokkha'") is False
    assert is_multi_word_correction("'teeth' -> 'deaf'") is False
    assert is_multi_word_correction("Should be 'vinaya'") is False


def test_is_multi_word_correction_multi_word() -> None:
    assert (
        is_multi_word_correction("'completion nation' -> 'complete cessation'") is True
    )
    assert is_multi_word_correction("'polyvots' -> 'body parts'") is True
    assert is_multi_word_correction("'five cents' -> 'five senses'") is True


def test_is_multi_word_correction_single_correction_from_multi_original() -> None:
    assert is_multi_word_correction("'a nature' -> 'anicca'") is False
    assert is_multi_word_correction("'in a niche' -> 'dukkha'") is False


def test_is_multi_word_correction_proper_name() -> None:
    assert is_multi_word_correction("'motor dummy car' -> 'Moti Dhammika'") is False
    assert is_multi_word_correction("'Wapan Manachai' -> 'Wat Pa Nanachat'") is False
    assert is_multi_word_correction("'Sgt. Brahms' -> 'Ajahn Brahm'") is False


def test_enforce_single_word_rule_downgrade() -> None:
    findings: list[dict[str, str]] = [
        {
            "passage": "zealous furry fox",
            "classification": "TP-fix",
            "reason": "ok",
            "suggestion": "'completion nation' -> 'complete cessation'",
        },
        {
            "passage": "Bhatimokha",
            "classification": "TP-fix",
            "reason": "ok",
            "suggestion": "'Bhatimokha' -> 'Patimokkha'",
        },
    ]
    result = enforce_single_word_rule(findings)

    assert result[0]["classification"] == "TP-defer"
    assert "DOWNGRADED" in result[0]["reason"]
    assert result[1]["classification"] == "TP-fix"  # single word correction, unchanged


def test_enforce_single_word_rule_no_op() -> None:
    findings: list[dict[str, str]] = [
        {
            "passage": "a nature",
            "classification": "FP",
            "reason": "fp",
            "suggestion": "'a nature' -> 'anicca'",
        },
        {
            "passage": "multi word passage",
            "classification": "TP-defer",
            "reason": "need review",
            "suggestion": "multi word",
        },
    ]
    result = enforce_single_word_rule(findings)
    assert result[0]["classification"] == "FP"
    assert result[1]["classification"] == "TP-defer"


def test_format_compact() -> None:
    findings: list[dict[str, str]] = [
        {
            "passage": "Bhatimokha",
            "classification": "TP-fix",
            "reason": "direct phonetic",
        },
        {
            "passage": "the the eye",
            "classification": "TP-fix",
            "reason": "duplicate word",
        },
    ]
    output = format_compact(findings)

    lines = output.split("\n")
    assert len(lines) == 2
    assert "TP-fix" in lines[0]
    assert "Bhatimokha" in lines[0]
    assert "TP-fix" in lines[1]


def test_format_compact_escapes_pipes() -> None:
    findings: list[dict[str, str]] = [
        {"passage": "text | with pipe", "classification": "FP", "reason": "has | pipe"},
    ]
    output = format_compact(findings)
    assert "text \\| with pipe" in output
    assert "has \\| pipe" in output


def test_build_classification_instruction_includes_patterns() -> None:
    instruction = build_classification_instruction(
        "- 'teams' -> 'temples' [stage: semantic]", ""
    )
    assert "teams" in instruction
    assert "temples" in instruction
    assert "PHONETIC COVERAGE RULE" in instruction


def test_build_classification_instruction_includes_reference() -> None:
    instruction = build_classification_instruction("", "DO NOT FLAG: some rule")
    assert "DO NOT FLAG: some rule" in instruction


def test_load_carried_patterns_no_file_returns_empty() -> None:
    result = load_carried_patterns(Path("/nonexistent/path.md"))
    assert result == ""


def test_load_carried_patterns_extracts_semantic_tags(tmp_path: Path) -> None:
    hub = tmp_path / "hub.md"
    hub.write_text(
        """# Enhance State

## Carried Patterns
- 'teams' -> 'temples' [stage: semantic]
- 'dog' -> 'Dhamma talk' [stage: semantic, pali]
- 'winner' -> 'Vinaya' [stage: pali]
- 'chimes' -> 'themes' [stage: semantic]
- unrelated pattern [stage: polish]
""",
        encoding="utf-8",
    )

    result = load_carried_patterns(hub)

    assert "teams" in result
    assert "dog" in result
    assert "chimes" in result
    assert "winner" not in result
    assert "unrelated" not in result


def test_load_carried_patterns_no_semantic_tag(tmp_path: Path) -> None:
    hub = tmp_path / "hub.md"
    hub.write_text(
        """# Enhance State

## Carried Patterns
- 'winner' -> 'Vinaya' [stage: pali]
- unrelated pattern [stage: polish]
""",
        encoding="utf-8",
    )

    result = load_carried_patterns(hub)
    assert result == ""
