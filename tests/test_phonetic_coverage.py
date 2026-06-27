"""Test enforce_phonetic_coverage_rule() against known-good/bad examples from the backlog."""

import pytest
from tests.fixtures.phonetic_coverage_examples import PHONETIC_EXAMPLES
from tools.semantic_classify import enforce_phonetic_coverage_rule


@pytest.mark.parametrize("passage,suggestion,expected", PHONETIC_EXAMPLES)
def test_phonetic_coverage_rule(passage: str, suggestion: str, expected: str) -> None:
    findings = [
        {
            "classification": "TP-fix",
            "passage": passage,
            "suggestion": suggestion,
            "reason": "",
        }
    ]
    result = enforce_phonetic_coverage_rule(findings)
    actual = "downgrade" if result[0]["classification"] == "TP-defer" else "keep"
    assert actual == expected, (
        f"passage='{passage}' suggestion='{suggestion}' expected={expected} got={actual}"
    )
