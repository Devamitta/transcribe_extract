"""Tests Antigravity CLI provider routing and model fallback behavior."""

import importlib
import json
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tools.antigravity_cli_models import CommandResult


ProviderModule = Any


def _work_models(provider_name: str) -> list[str]:
    """Read a provider's work model list from the single source of truth."""
    data = json.loads(Path("tools/ai_models.json").read_text(encoding="utf-8"))
    return data["provider_models"][provider_name]["work"]


# Work models for antigravity-cli, sourced from ai_models.json so model tuning
# in the JSON does not break these routing/rotation assertions.
ANTIGRAVITY_WORK_MODELS = _work_models("antigravity-cli")


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
    original_antigravity_cli = sys.modules.get("tools.antigravity_cli")
    tools_package = sys.modules.get("tools")
    had_provider_attr = tools_package is not None and hasattr(tools_package, "provider")
    original_provider_attr = (
        getattr(tools_package, "provider", None) if had_provider_attr else None
    )

    def _load(
        provider_name: str,
        argv: list[str],
        key_results: dict[str, bool],
        generate_failures: set[str],
    ) -> tuple[ProviderModule, list[str], list[str]]:
        sys.modules.pop("tools.provider", None)
        current_tools_package = sys.modules.get("tools")
        if current_tools_package is not None and hasattr(
            current_tools_package, "provider"
        ):
            delattr(current_tools_package, "provider")
        checked_models: list[str] = []
        generated_models: list[str] = []

        fake_antigravity_cli = ModuleType("tools.antigravity_cli")

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

        setattr(fake_antigravity_cli, "get_working_key", fake_get_working_key)
        setattr(fake_antigravity_cli, "generate_content", fake_generate_content)

        monkeypatch.setitem(sys.modules, "tools.antigravity_cli", fake_antigravity_cli)
        monkeypatch.setenv("PROVIDER", provider_name)
        monkeypatch.setattr(sys, "argv", argv)

        provider = importlib.import_module("tools.provider")
        return provider, checked_models, generated_models

    yield _load

    sys.modules.pop("tools.provider", None)
    if original_provider is not None:
        sys.modules["tools.provider"] = original_provider
    current_tools_package = sys.modules.get("tools")
    if current_tools_package is not None:
        if had_provider_attr:
            setattr(current_tools_package, "provider", original_provider_attr)
        elif hasattr(current_tools_package, "provider"):
            delattr(current_tools_package, "provider")
    if original_antigravity_cli is not None:
        sys.modules["tools.antigravity_cli"] = original_antigravity_cli


def test_antigravity_cli_provider_uses_requested_work_model_order(
    load_provider: Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
) -> None:
    provider, checked_models, _ = load_provider(
        "antigravity-cli",
        ["script.py"],
        {
            ANTIGRAVITY_WORK_MODELS[0]: True,
            ANTIGRAVITY_WORK_MODELS[1]: False,
        },
        set(),
    )

    assert provider.ANTIGRAVITY_CLI_WORK_MODELS == ANTIGRAVITY_WORK_MODELS
    assert provider.get_working_key() is True
    assert checked_models == [ANTIGRAVITY_WORK_MODELS[0]]


def test_antigravity_cli_dry_run_uses_low_flash(
    load_provider: Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
) -> None:
    provider, checked_models, _ = load_provider(
        "antigravity-cli",
        ["script.py", "--dry-run"],
        {"Gemini 3.5 Flash (Low)": True},
        set(),
    )

    assert provider.CLI_TEST_MODE is True
    assert provider.ANTIGRAVITY_CLI_TEST_MODELS == ["Gemini 3.5 Flash (Low)"]
    assert provider.get_working_key() is True
    assert checked_models == ["Gemini 3.5 Flash (Low)"]


def test_antigravity_cli_generation_rotates_to_next_model_on_failure(
    load_provider: Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
) -> None:
    provider, _, generated_models = load_provider(
        "antigravity-cli",
        ["script.py"],
        {},
        {ANTIGRAVITY_WORK_MODELS[0]},
    )

    result = provider.generate_content("content", "system")

    assert result.endswith(f":{ANTIGRAVITY_WORK_MODELS[1]}")
    assert generated_models == [
        ANTIGRAVITY_WORK_MODELS[0],
        ANTIGRAVITY_WORK_MODELS[1],
    ]


def test_agy_provider_alias_uses_same_models(
    load_provider: Callable[
        [str, list[str], dict[str, bool], set[str]],
        tuple[ProviderModule, list[str], list[str]],
    ],
) -> None:
    provider, checked_models, _ = load_provider(
        "agy",
        ["script.py", "-t"],
        {"Gemini 3.5 Flash (Low)": True},
        set(),
    )

    assert provider.PROVIDER == "agy"
    assert provider.get_working_key() is True
    assert checked_models == ["Gemini 3.5 Flash (Low)"]


def test_antigravity_cli_generate_content_uses_print_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import antigravity_cli

    captured: dict[str, object] = {}

    def fake_run_antigravity_print(
        cli_path: Path,
        model_name: str,
        prompt: str,
        *,
        timeout: int,
    ) -> CommandResult:
        captured["cli_path"] = cli_path
        captured["model_name"] = model_name
        captured["prompt"] = prompt
        captured["timeout"] = timeout
        return CommandResult(
            command=["agy"],
            returncode=0,
            stdout='{"response": "done"}',
            stderr=None,
        )

    monkeypatch.setattr(
        antigravity_cli, "locate_executable", lambda name: Path("/usr/local/bin/agy")
    )
    monkeypatch.setattr(
        antigravity_cli, "run_antigravity_print", fake_run_antigravity_print
    )

    result = antigravity_cli.generate_content(
        contents="source text",
        system_instruction="summarize",
        model="Gemini 3.1 Pro (Low)",
        max_output_tokens=123,
        temperature=0.2,
        timeout=45,
    )

    assert result == "done"
    assert captured["cli_path"] == Path("/usr/local/bin/agy")
    assert captured["model_name"] == "Gemini 3.1 Pro (Low)"
    assert captured["timeout"] == 45
    prompt = captured["prompt"]
    assert isinstance(prompt, str)
    assert "SYSTEM INSTRUCTION:\nsummarize" in prompt
    assert "USER CONTENT:\nsource text" in prompt
