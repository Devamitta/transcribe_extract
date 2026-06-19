from pathlib import Path

from scripts.evaluate_batch import (
    is_flagged,
    discover_pairs,
    write_report,
    EvalResult,
)
from tools.eval_judge import (
    CriterionScore,
    DeterministicCheck,
    JudgeParseResult,
)


def test_is_flagged():
    # all scores 5 + ratio 0.80 -> False
    assert not is_flagged(
        {"c1": CriterionScore(5, ""), "c2": CriterionScore(5, "")}, 0.80
    )

    # one score 3 + ratio 0.80 -> True
    assert is_flagged({"c1": CriterionScore(3, ""), "c2": CriterionScore(5, "")}, 0.80)

    # all scores 5 + ratio 0.55 -> True
    assert is_flagged({"c1": CriterionScore(5, ""), "c2": CriterionScore(5, "")}, 0.55)

    # all scores 4 + ratio 0.60 -> False (both thresholds exclusive)
    assert not is_flagged(
        {"c1": CriterionScore(4, ""), "c2": CriterionScore(4, "")}, 0.60
    )

    # all scores 5 + ratio 0.46 (legit short talk) -> True via ratio floor
    assert is_flagged({"c1": CriterionScore(5, ""), "c2": CriterionScore(5, "")}, 0.46)


def test_discover_pairs(tmp_path):
    # Setup mock structure
    (tmp_path / "output/corrected_pali/test").mkdir(parents=True)
    (tmp_path / "output/extracted/test").mkdir(parents=True)

    # NFD source, NFC candidate
    source_nfd = "a\u0304.md"  # ā decomposed
    cand_nfc = "\u0101.md"  # ā composed
    (tmp_path / "output/corrected_pali/test" / source_nfd).touch()
    (tmp_path / "output/extracted/test" / cand_nfc).touch()

    # Source without candidate
    (tmp_path / "output/corrected_pali/test/no_cand.md").touch()

    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        pairs = discover_pairs("extract", "test", None)
        assert len(pairs) == 1
        assert (
            "a\u0304.md" in pairs[0].source_path.name
            or "\u0101.md" in pairs[0].source_path.name
        )
        assert pairs[0].candidate_path.name == cand_nfc

        pairs_limit = discover_pairs("extract", "test", 0)
        assert len(pairs_limit) == 0
    finally:
        os.chdir(original_cwd)


def test_write_report(tmp_path):
    report_path = tmp_path / "report.md"
    results = [
        # Clean
        EvalResult(
            source_path=Path("s1.md"),
            candidate_path=Path("c1.md"),
            judge=JudgeParseResult(
                ok=True, scores={"c1": CriterionScore(5, "good")}, error=None
            ),
            deterministic_checks=[],
            size_ratio=0.8,
            error=None,
        ),
        # Flagged by score
        EvalResult(
            source_path=Path("s2.md"),
            candidate_path=Path("c2.md"),
            judge=JudgeParseResult(
                ok=True, scores={"c1": CriterionScore(3, "bad")}, error=None
            ),
            deterministic_checks=[DeterministicCheck("chk", True, "ok")],
            size_ratio=0.8,
            error=None,
        ),
        # Flagged by ratio
        EvalResult(
            source_path=Path("s3.md"),
            candidate_path=Path("c3.md"),
            judge=JudgeParseResult(
                ok=True, scores={"c1": CriterionScore(5, "good")}, error=None
            ),
            deterministic_checks=[],
            size_ratio=0.5,
            error=None,
        ),
        # Flagged by judge error
        EvalResult(
            source_path=Path("s4.md"),
            candidate_path=Path("c4.md"),
            judge=JudgeParseResult(ok=False, scores={}, error="failed"),
            deterministic_checks=[],
            size_ratio=0.8,
            error=None,
        ),
    ]

    write_report(report_path, results, "extract", "test", "2024")
    content = report_path.read_text()

    assert "- Pairs evaluated: 4" in content
    assert "- Flagged: 3   |   Clean: 1" in content
    assert "### c1.md" not in content
    assert "### c2.md" in content
    assert "### c3.md" in content
    assert "### c4.md" in content
    assert "c1: 3/5 — bad" in content
    assert "Deterministic `chk`: pass — ok" in content
    assert "Judge error: failed" in content
