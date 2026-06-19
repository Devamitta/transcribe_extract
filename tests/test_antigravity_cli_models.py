"""Tests for normalizing Antigravity CLI model-list output."""

import json
from pathlib import Path

import pytest

from tools import antigravity_cli_models
from tools.antigravity_cli_models import (
    PROBE_PROMPT,
    AntigravityCliModelError,
    CommandResult,
    SourceMetadata,
    normalize_registry,
    probe_model,
)


def _source() -> SourceMetadata:
    return SourceMetadata(
        cli_path=Path("/usr/local/bin/agy"),
        cli_version="1.0.6",
        list_command=["/usr/local/bin/agy", "models"],
    )


def test_text_output_models_are_normalized() -> None:
    raw_output = """
    \x1b[?25lFetching available models...
    • Gemini 3.5 Flash (Low) current
    • Gemini 3.1 Pro (Low)
    • Claude Sonnet 4.6 (thinking)
    • GPT-OSS-120b (Medium)
    """

    registry = normalize_registry(raw_output, _source())

    models = registry.display_models()
    assert [model.name for model in models] == [
        "Gemini 3.5 Flash (Low)",
        "Gemini 3.1 Pro (Low)",
        "Claude Sonnet 4.6 (thinking)",
        "GPT-OSS-120b (Medium)",
    ]
    assert models[0].provider == "google"
    assert models[0].tier == "high"
    assert models[0].is_default is True
    assert models[2].provider == "anthropic"
    assert models[3].provider == "openai"


def test_table_output_models_are_normalized() -> None:
    raw_output = """
    Name                          Provider     Status
    ----------------------------  --------     -------
    * Gemini 3.1 Pro (High)       Google       default
      Claude Opus 4.6 (thinking)  Anthropic    available
    """

    registry = normalize_registry(raw_output, _source())

    models = registry.display_models()
    assert [model.name for model in models] == [
        "Gemini 3.1 Pro (High)",
        "Claude Opus 4.6 (thinking)",
    ]
    assert models[0].is_default is True
    assert models[1].tier == "thinking"


def test_json_output_models_are_normalized() -> None:
    raw_output = json.dumps(
        {
            "models": [
                {
                    "displayName": "Gemini 3.5 Flash (Low)",
                    "id": "gemini-rainsong",
                    "provider": "google",
                    "tier": "high",
                    "isDefault": True,
                },
                "Claude Sonnet 4.6 (thinking)",
            ]
        }
    )

    registry = normalize_registry(raw_output, _source())
    output = registry.to_json()
    models = output["models"]

    assert isinstance(models, list)
    assert models[0] == {
        "name": "Gemini 3.5 Flash (Low)",
        "model_id": "gemini-rainsong",
        "provider": "google",
        "tier": "high",
        "is_default": True,
        "raw_line": (
            '{"displayName": "Gemini 3.5 Flash (Low)", "id": '
            '"gemini-rainsong", "isDefault": true, "provider": "google", '
            '"tier": "high"}'
        ),
    }
    assert output["account_availability"] == {
        "status": "checked_by_models_command",
        "note": "`agy models` returned the available model list.",
    }


def test_sign_in_required_output_raises_clear_error() -> None:
    with pytest.raises(AntigravityCliModelError, match="sign-in is required"):
        normalize_registry(
            "Error: Please sign in to view available models.",
            _source(),
        )


def test_load_registry_uses_models_command_with_optional_log_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_locate_executable(name: str) -> Path:
        captured["name"] = name
        return Path("/usr/local/bin/agy")

    def fake_version(cli_path: Path) -> str:
        captured["version_path"] = cli_path
        return "1.0.6"

    def fake_run_cli_command(
        command: list[str],
        *,
        timeout: int,
        use_pty: bool = True,
    ) -> CommandResult:
        captured["command"] = command
        captured["timeout"] = timeout
        captured["use_pty"] = use_pty
        return CommandResult(
            command=command,
            returncode=0,
            stdout="Gemini 3.5 Flash (Low)",
            stderr=None,
        )

    monkeypatch.setattr(
        antigravity_cli_models, "locate_executable", fake_locate_executable
    )
    monkeypatch.setattr(antigravity_cli_models, "run_antigravity_version", fake_version)
    monkeypatch.setattr(
        antigravity_cli_models, "_run_cli_command", fake_run_cli_command
    )

    registry = antigravity_cli_models.load_registry(
        timeout=33,
        log_file=Path("temp/agy-models.log"),
    )

    assert registry.source.cli_version == "1.0.6"
    assert captured["name"] == "agy"
    assert captured["version_path"] == Path("/usr/local/bin/agy")
    assert captured["command"] == [
        "/usr/local/bin/agy",
        "--log-file",
        "temp/agy-models.log",
        "models",
    ]
    assert captured["timeout"] == 33
    assert captured["use_pty"] is True


def test_probe_model_uses_print_command_with_model_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_cli_command(
        command: list[str],
        *,
        timeout: int,
        use_pty: bool = True,
    ) -> CommandResult:
        captured["command"] = command
        captured["timeout"] = timeout
        captured["use_pty"] = use_pty
        return CommandResult(command=command, returncode=0, stdout="OK", stderr=None)

    monkeypatch.setattr(
        antigravity_cli_models, "_run_cli_command", fake_run_cli_command
    )

    result = probe_model(
        Path("/usr/local/bin/agy"),
        "Gemini 3.1 Pro (High)",
        timeout=60,
        log_file=Path("temp/agy-print.log"),
    )

    assert result.status == "ok"
    assert result.response_text == "OK"
    assert captured["command"] == [
        "/usr/local/bin/agy",
        "--log-file",
        "temp/agy-print.log",
        "--model",
        "Gemini 3.1 Pro (High)",
        "--print-timeout",
        "60s",
        "--print",
        PROBE_PROMPT,
    ]
    assert captured["timeout"] == 65
    assert captured["use_pty"] is True
