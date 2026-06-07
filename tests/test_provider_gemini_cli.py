"""Tests Gemini CLI provider routing and model fallback behavior."""

import importlib
import json
import subprocess
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


ProviderModule = Any


@pytest.fixture()
def load_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[
    Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
    None,
    None,
]:
    original_provider = sys.modules.get("tools.provider")
    original_gemini = sys.modules.get("tools.gemini")
    original_gemini_cli = sys.modules.get("tools.gemini_cli")

    def _load(
        provider_name: str,
        argv: list[str],
        key_results: dict[str, bool],
        generate_failures: set[str],
    ) -> tuple[ProviderModule, list[str], list[str]]:
        sys.modules.pop("tools.provider", None)
        checked_models: list[str] = []
        generated_models: list[str] = []

        fake_gemini = ModuleType("tools.gemini")
        fake_gemini_cli = ModuleType("tools.gemini_cli")

        def fake_get_working_key(model: str) -> bool:
            checked_models.append(model)
            return key_results.get(model, False)

        def fake_generate_content(
            contents: str,
            system_instruction: str,
            model: str,
            max_output_tokens: int = 32768,
            temperature: float = 0.1,
        ) -> str:
            generated_models.append(model)
            if model in generate_failures:
                raise RuntimeError(f"{model} failed")
            return f"{contents}:{system_instruction}:{max_output_tokens}:{temperature}:{model}"

        for module in (fake_gemini, fake_gemini_cli):
            setattr(module, "get_working_key", fake_get_working_key)
            setattr(module, "generate_content", fake_generate_content)

        monkeypatch.setitem(sys.modules, "tools.gemini", fake_gemini)
        monkeypatch.setitem(sys.modules, "tools.gemini_cli", fake_gemini_cli)
        monkeypatch.setenv("PROVIDER", provider_name)
        monkeypatch.setattr(sys, "argv", argv)

        provider = importlib.import_module("tools.provider")
        return provider, checked_models, generated_models

    yield _load

    sys.modules.pop("tools.provider", None)
    if original_provider is not None:
        sys.modules["tools.provider"] = original_provider
    if original_gemini is not None:
        sys.modules["tools.gemini"] = original_gemini
    if original_gemini_cli is not None:
        sys.modules["tools.gemini_cli"] = original_gemini_cli


def test_google_provider_keeps_existing_gemini_api_defaults(
    load_provider: Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
) -> None:
    provider, checked_models, _ = load_provider(
        "google",
        ["script.py", "--dry-run"],
        {"gemini-2.5-flash": True},
        set(),
    )

    assert provider.TEST_MODE is False
    assert provider.CLI_TEST_MODE is True
    assert provider.GEMINI_WORK_MODELS == ["gemini-2.5-flash"]
    assert provider.GEMINI_TEST_MODELS == ["gemini-3.1-flash-lite-preview"]
    assert provider.get_working_key() is True
    assert checked_models == ["gemini-2.5-flash"]


def test_gemini_cli_provider_uses_requested_work_model_order(
    load_provider: Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
) -> None:
    provider, checked_models, _ = load_provider(
        "gemini-cli",
        ["script.py"],
        {
            "gemini-3.1-pro-preview": False,
            "gemini-2.5-pro": True,
            "gemini-3-flash-preview": True,
        },
        set(),
    )

    assert provider.GEMINI_CLI_WORK_MODELS == [
        "gemini-3.1-pro-preview",
        "gemini-2.5-pro",
        "gemini-3-flash-preview",
    ]
    assert provider.get_working_key() is True
    assert checked_models == ["gemini-3.1-pro-preview", "gemini-2.5-pro"]


def test_gemini_cli_dry_run_uses_flash_lite(
    load_provider: Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
) -> None:
    provider, checked_models, _ = load_provider(
        "gemini-cli",
        ["script.py", "--dry-run"],
        {"gemini-3.1-flash-lite": True},
        set(),
    )

    assert provider.CLI_TEST_MODE is True
    assert provider.GEMINI_CLI_TEST_MODELS == ["gemini-3.1-flash-lite"]
    assert provider.get_working_key() is True
    assert checked_models == ["gemini-3.1-flash-lite"]


def test_gemini_cli_generation_rotates_to_next_model_on_failure(
    load_provider: Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
) -> None:
    provider, _, generated_models = load_provider(
        "gemini-cli",
        ["script.py"],
        {},
        {"gemini-3.1-pro-preview"},
    )

    result = provider.generate_content("content", "system")

    assert result.endswith(":gemini-2.5-pro")
    assert generated_models == ["gemini-3.1-pro-preview", "gemini-2.5-pro"]


def test_gemini_cli_generate_content_uses_headless_json_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import gemini_cli

    captured: dict[str, Any] = {}

    def fake_run(
        command: list[str],
        capture_output: bool,
        check: bool,
        stdin: int,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["capture_output"] = capture_output
        captured["check"] = check
        captured["stdin"] = stdin
        captured["text"] = text
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"response": "done"}),
            stderr="",
        )

    monkeypatch.setattr(
        gemini_cli.shutil, "which", lambda name: "/opt/homebrew/bin/gemini"
    )
    monkeypatch.setattr(gemini_cli.subprocess, "run", fake_run)

    result = gemini_cli.generate_content(
        contents="source text",
        system_instruction="summarize",
        model="gemini-3.1-pro-preview",
        max_output_tokens=123,
        temperature=0.2,
        timeout=45,
    )

    assert result == "done"
    assert captured["timeout"] == 45
    assert captured["stdin"] == subprocess.DEVNULL
    assert captured["command"][:4] == [
        str(Path("/opt/homebrew/bin/gemini")),
        "-m",
        "gemini-3.1-pro-preview",
        "-p",
    ]
    assert "--output-format" in captured["command"]
    assert "json" in captured["command"]
    assert "--approval-mode" in captured["command"]
    assert "plan" in captured["command"]
    assert "-e" in captured["command"]
    assert "none" in captured["command"]
    prompt = captured["command"][captured["command"].index("-p") + 1]
    assert "SYSTEM INSTRUCTION:\nsummarize" in prompt
    assert "USER CONTENT:\nsource text" in prompt


def test_gemini_cli_get_working_key_uses_realistic_probe_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import gemini_cli

    captured: dict[str, Any] = {}

    def fake_generate_content(
        contents: str,
        system_instruction: str,
        model: str,
        max_output_tokens: int,
        temperature: float,
        timeout: int,
    ) -> str:
        captured["contents"] = contents
        captured["system_instruction"] = system_instruction
        captured["model"] = model
        captured["max_output_tokens"] = max_output_tokens
        captured["temperature"] = temperature
        captured["timeout"] = timeout
        return "OK"

    monkeypatch.setattr(gemini_cli, "generate_content", fake_generate_content)

    assert gemini_cli.get_working_key("gemini-3.1-pro-preview") is True
    assert captured == {
        "contents": "Return OK only.",
        "system_instruction": "Return exactly OK and nothing else.",
        "model": "gemini-3.1-pro-preview",
        "max_output_tokens": 10,
        "temperature": 0.0,
        "timeout": 60,
    }
