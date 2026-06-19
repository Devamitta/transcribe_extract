"""Regression tests for the shared chunk runner."""

import json
from pathlib import Path

from tools.chunk_runner import (
    EXIT_OK,
    EXIT_PARTIAL,
    RunnerConfig,
    discover_files,
    run,
)
from tools.incremental import get_temp_path


def test_success_path_writes_output_and_deletes_temp(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_file = input_dir / "sub" / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("one|two", encoding="utf-8")
    calls: list[str] = []

    def generate(chunk: str, _file_path: Path) -> str:
        calls.append(chunk)
        return chunk.upper()

    config = RunnerConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        chunker=lambda text: text.split("|"),
        generate=generate,
        label="testing",
    )

    result = run(config)
    output_file = output_dir / "sub" / "talk.md"

    assert result.exit_code == EXIT_OK
    assert calls == ["one", "two"]
    assert output_file.read_text(encoding="utf-8") == "ONE\n\nTWO"
    assert not get_temp_path(output_file).exists()


def test_interrupted_run_resumes_without_recalling_completed_chunks(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_file = input_dir / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("one|two", encoding="utf-8")
    output_file = output_dir / "talk.md"
    temp_file = get_temp_path(output_file)
    temp_file.parent.mkdir(parents=True)
    temp_file.write_text(json.dumps(["ONE"]), encoding="utf-8")
    calls: list[str] = []

    def generate(chunk: str, _file_path: Path) -> str:
        calls.append(chunk)
        return chunk.upper()

    config = RunnerConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        chunker=lambda text: text.split("|"),
        generate=generate,
        label="testing",
    )

    result = run(config)

    assert result.exit_code == EXIT_OK
    assert calls == ["two"]
    assert output_file.read_text(encoding="utf-8") == "ONE\n\nTWO"
    assert not temp_file.exists()


def test_persistently_failing_chunk_keeps_temp_and_writes_no_output(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_file = input_dir / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("good|bad", encoding="utf-8")
    calls: list[str] = []

    def generate(chunk: str, _file_path: Path) -> str:
        calls.append(chunk)
        if chunk == "bad":
            raise RuntimeError("provider failed")
        return chunk.upper()

    config = RunnerConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        chunker=lambda text: text.split("|"),
        generate=generate,
        label="testing",
    )

    result = run(config)
    output_file = output_dir / "talk.md"
    temp_file = get_temp_path(output_file)

    assert result.exit_code == EXIT_PARTIAL
    assert calls.count("bad") == 9
    assert result.files[0].failed_chunks == [1]
    assert not output_file.exists()
    assert json.loads(temp_file.read_text(encoding="utf-8")) == ["GOOD", None]


def test_failing_per_chunk_validation_retries_then_fails(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_file = input_dir / "talk.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("source", encoding="utf-8")
    calls = 0

    def generate(_chunk: str, _file_path: Path) -> str:
        nonlocal calls
        calls += 1
        return "too short"

    config = RunnerConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        chunker=lambda text: [text],
        generate=generate,
        validator=lambda _chunk, result, _file_path, _index: result == "accepted",
        label="testing",
    )

    result = run(config)

    assert result.exit_code == EXIT_PARTIAL
    assert calls == 9
    assert result.files[0].failed_chunks == [0]
    assert not (output_dir / "talk.md").exists()


def test_discover_files_skips_existing_outputs_and_applies_limit(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    (input_dir / "a.md").write_text("a", encoding="utf-8")
    (input_dir / "b.md").write_text("b", encoding="utf-8")
    (input_dir / "c.md").write_text("c", encoding="utf-8")
    (output_dir / "a.md").write_text("done", encoding="utf-8")

    config = RunnerConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        chunker=lambda text: [text],
        generate=lambda chunk, _file_path: chunk,
        label="testing",
    )

    result = discover_files(config, limit=1)

    assert result.discovered == 3
    assert result.skipped_existing == 1
    assert [item.input_path.name for item in result.queue] == ["b.md"]
