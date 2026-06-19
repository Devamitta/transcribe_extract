"""Tests the stage-evaluation CLI with mocked LLM providers."""

import json
from pathlib import Path

import pytest

from scripts import evaluate_stages
from tools.eval_judge import DeterministicCheck, EXTRACT_CRITERIA, JudgeParseResult


def _write_golden_tree(root: Path, stages: tuple[str, ...], count: int = 3) -> None:
    source = " ".join(f"word{i}" for i in range(100))
    for stage in stages:
        stage_dir = root / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, count + 1):
            (stage_dir / f"{index:02d}_{stage}.md").write_text(
                source,
                encoding="utf-8",
            )


def _judge_json(score: int = 4) -> str:
    return json.dumps(
        {
            criterion.key: {
                "score": score,
                "reason": f"{criterion.key} cites word0",
            }
            for criterion in EXTRACT_CRITERIA
        }
    )


@pytest.fixture()
def configured_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    monkeypatch.chdir(tmp_path)
    golden_root = tmp_path / "eval" / "golden"
    report_dir = tmp_path / "reports" / "eval"
    monkeypatch.setattr(evaluate_stages, "GOLDEN_ROOT", golden_root)
    monkeypatch.setattr(evaluate_stages, "REPORT_DIR", report_dir)
    monkeypatch.setattr(evaluate_stages, "HISTORY_PATH", report_dir / "history.json")
    monkeypatch.setattr(evaluate_stages, "INTER_CALL_PACING_SECONDS", 0)
    monkeypatch.setattr(evaluate_stages.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(evaluate_stages, "probe_judge_model", lambda: True)
    monkeypatch.setattr(
        evaluate_stages,
        "active_generation_models",
        lambda: ["Gemini 3.5 Flash (Low)"],
    )
    return golden_root


def test_stage_limit_and_test_selection(
    configured_cli: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_golden_tree(configured_cli, ("extract",), count=3)
    generated: list[str] = []

    def fake_generate(
        config: evaluate_stages.StageEvalConfig,
        _source_path: Path,
        _prepared_source: str,
    ) -> str:
        generated.append(config.name)
        return " ".join(f"candidate{i}" for i in range(80))

    monkeypatch.setattr(evaluate_stages, "generate_candidate", fake_generate)
    monkeypatch.setattr(
        evaluate_stages,
        "judge_candidate",
        lambda _config, _source, _candidate: _judge_json(),
    )

    exit_code = evaluate_stages.main(["--stage", "extract", "--test"])

    assert exit_code == 0
    assert generated == ["extract", "extract"]


def test_resume_skips_saved_excerpts(
    configured_cli: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_golden_tree(configured_cli, ("extract",), count=2)
    first_saved = evaluate_stages.ExcerptResult(
        stage="extract",
        excerpt_path=str(configured_cli / "extract" / "01_extract.md"),
        source_path=str(configured_cli / "extract" / "01_extract.md"),
        judge=JudgeParseResult(
            ok=True,
            scores={
                criterion.key: evaluate_stages.CriterionScore(
                    score=4,
                    reason=f"{criterion.key} cites word0",
                )
                for criterion in EXTRACT_CRITERIA
            },
        ),
        deterministic_checks=[
            DeterministicCheck(
                name="extract_min_word_ratio",
                passed=True,
                details="candidate/source word ratio 80.0%",
            )
        ],
    )
    temp_path = evaluate_stages.get_stage_temp_path("extract")
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(
        json.dumps([evaluate_stages.serialize_result(first_saved)]),
        encoding="utf-8",
    )
    generated_paths: list[Path] = []

    def fake_generate(
        _config: evaluate_stages.StageEvalConfig,
        source_path: Path,
        _prepared_source: str,
    ) -> str:
        generated_paths.append(source_path)
        return " ".join(f"candidate{i}" for i in range(80))

    monkeypatch.setattr(evaluate_stages, "generate_candidate", fake_generate)
    monkeypatch.setattr(
        evaluate_stages,
        "judge_candidate",
        lambda _config, _source, _candidate: _judge_json(),
    )

    exit_code = evaluate_stages.main(["--stage", "extract"])

    assert exit_code == 0
    assert generated_paths == [configured_cli / "extract" / "02_extract.md"]
    assert not temp_path.exists()


def test_report_and_history_are_written(
    configured_cli: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_golden_tree(configured_cli, ("extract",), count=1)
    monkeypatch.setattr(
        evaluate_stages,
        "generate_candidate",
        lambda _config, _source_path, _prepared_source: " ".join(
            f"candidate{i}" for i in range(80)
        ),
    )
    monkeypatch.setattr(
        evaluate_stages,
        "judge_candidate",
        lambda _config, _source, _candidate: _judge_json(),
    )

    exit_code = evaluate_stages.main(["--stage", "extract", "--limit", "1"])

    assert exit_code == 0
    report_files = list(
        (configured_cli.parent.parent / "reports" / "eval").glob("eval_*.md")
    )
    assert len(report_files) == 1
    report = report_files[0].read_text(encoding="utf-8")
    assert "Overall mean: 4.00" in report
    history = json.loads(
        (configured_cli.parent.parent / "reports" / "eval" / "history.json").read_text(
            encoding="utf-8"
        )
    )
    assert history[0]["stage"] == "extract"
    assert history[0]["overall_mean"] == 4.0
    assert history[0]["run_mode"] == "limited"
    assert history[0]["sampled"] is True


def test_full_run_regression_returns_exit_code_two(
    configured_cli: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_golden_tree(configured_cli, ("extract",), count=1)
    history_path = configured_cli.parent.parent / "reports" / "eval" / "history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(
            [
                {
                    "stage": "extract",
                    "overall_mean": 5.0,
                    "excerpt_count": 1,
                    "run_mode": "full",
                    "sampled": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        evaluate_stages,
        "generate_candidate",
        lambda _config, _source_path, _prepared_source: " ".join(
            f"candidate{i}" for i in range(80)
        ),
    )
    monkeypatch.setattr(
        evaluate_stages,
        "judge_candidate",
        lambda _config, _source, _candidate: _judge_json(score=4),
    )

    exit_code = evaluate_stages.main(["--stage", "extract"])

    assert exit_code == 2


def test_sampled_run_skips_regression_gate(
    configured_cli: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_golden_tree(configured_cli, ("extract",), count=1)
    history_path = configured_cli.parent.parent / "reports" / "eval" / "history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(
            [
                {
                    "stage": "extract",
                    "overall_mean": 5.0,
                    "excerpt_count": 1,
                    "run_mode": "limited",
                    "sampled": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        evaluate_stages,
        "generate_candidate",
        lambda _config, _source_path, _prepared_source: " ".join(
            f"candidate{i}" for i in range(80)
        ),
    )
    monkeypatch.setattr(
        evaluate_stages,
        "judge_candidate",
        lambda _config, _source, _candidate: _judge_json(score=4),
    )

    exit_code = evaluate_stages.main(["--stage", "extract", "--limit", "1"])

    assert exit_code == 0
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert history[-1]["run_mode"] == "limited"
    assert history[-1]["sampled"] is True


def test_failed_stage_writes_report_but_not_history(
    configured_cli: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_golden_tree(configured_cli, ("extract",), count=1)

    def fail_generate(
        _config: evaluate_stages.StageEvalConfig,
        _source_path: Path,
        _prepared_source: str,
    ) -> str:
        raise TimeoutError

    monkeypatch.setattr(evaluate_stages, "generate_candidate", fail_generate)

    exit_code = evaluate_stages.main(["--stage", "extract", "--limit", "1"])

    assert exit_code == 1
    report_files = list(
        (configured_cli.parent.parent / "reports" / "eval").glob("eval_*.md")
    )
    assert len(report_files) == 1
    assert "TimeoutError" in report_files[0].read_text(encoding="utf-8")
    assert not (
        configured_cli.parent.parent / "reports" / "eval" / "history.json"
    ).exists()


def test_provider_env_is_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROVIDER", "google")

    probed = False

    def mock_probe() -> bool:
        nonlocal probed
        probed = True
        return False  # Stop execution after probe

    monkeypatch.setattr(evaluate_stages, "probe_judge_model", mock_probe)

    # If it ignores PROVIDER=google, it will call mock_probe and return 1 (from our False)
    # If it was gated, it would exit 1 BEFORE calling mock_probe.
    assert evaluate_stages.main(["--stage", "extract", "--test"]) == 1
    assert probed is True
