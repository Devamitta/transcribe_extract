"""Tests for normalizing Gemini CLI model registry data."""

from pathlib import Path
import subprocess
from typing import cast

import pytest

from tools.gemini_cli_models import (
    JsonObject,
    SourceMetadata,
    normalize_registry,
    probe_model,
)


def _source() -> SourceMetadata:
    return SourceMetadata(
        cli_path=Path("/usr/local/bin/gemini"),
        bundle_entry=Path(
            "/usr/local/lib/node_modules/@google/gemini-cli/bundle/gemini.js"
        ),
        bundle_dir=Path("/usr/local/lib/node_modules/@google/gemini-cli/bundle"),
        package_dir=Path("/usr/local/lib/node_modules/@google/gemini-cli"),
        package_version="0.45.0",
        cli_version="0.45.0",
        node_path=Path("/usr/local/bin/node"),
        source_module=Path(
            "/usr/local/lib/node_modules/@google/gemini-cli/bundle/dist-TEST.js"
        ),
        constants={"DEFAULT_GEMINI_MODEL": "gemini-2.5-pro"},
    )


def _registry_config() -> JsonObject:
    return cast(
        JsonObject,
        {
            "aliases": {
                "base": {"modelConfig": {"generateContentConfig": {"temperature": 0}}},
                "chat-base": {
                    "extends": "base",
                    "modelConfig": {
                        "generateContentConfig": {
                            "thinkingConfig": {"includeThoughts": True}
                        }
                    },
                },
                "gemini-3-pro-preview": {
                    "extends": "chat-base",
                    "modelConfig": {"model": "gemini-3-pro-preview"},
                },
                "gemini-3.1-pro-preview-customtools": {
                    "extends": "chat-base",
                    "modelConfig": {"model": "gemini-3.1-pro-preview-customtools"},
                },
                "gemini-2.5-flash": {
                    "extends": "chat-base",
                    "modelConfig": {"model": "gemini-2.5-flash"},
                },
                "classifier": {
                    "extends": "base",
                    "modelConfig": {"model": "flash-lite"},
                },
            },
            "modelDefinitions": {
                "gemini-3-pro-preview": {
                    "tier": "pro",
                    "family": "gemini-3",
                    "isPreview": True,
                    "isVisible": True,
                    "features": {"thinking": True, "multimodalToolUse": True},
                },
                "gemini-3.1-pro-preview-customtools": {
                    "tier": "pro",
                    "family": "gemini-3",
                    "isPreview": True,
                    "isVisible": False,
                    "features": {"thinking": True, "multimodalToolUse": True},
                },
                "gemini-2.5-flash": {
                    "tier": "flash",
                    "family": "gemini-2.5",
                    "isPreview": False,
                    "isVisible": True,
                    "features": {"thinking": False, "multimodalToolUse": False},
                },
                "auto": {
                    "displayName": "Auto",
                    "tier": "auto",
                    "isPreview": True,
                    "isVisible": True,
                    "features": {"thinking": True},
                },
                "pro": {
                    "tier": "pro",
                    "isPreview": False,
                    "isVisible": False,
                    "features": {"thinking": True},
                },
                "flash": {
                    "tier": "flash",
                    "isPreview": False,
                    "isVisible": False,
                    "features": {"thinking": False},
                },
                "flash-lite": {
                    "tier": "flash-lite",
                    "isPreview": False,
                    "isVisible": False,
                    "features": {"thinking": False},
                },
            },
            "modelIdResolutions": {
                "auto": {
                    "default": "gemini-3-pro-preview",
                    "contexts": [
                        {
                            "condition": {"hasAccessToPreview": False},
                            "target": "gemini-2.5-flash",
                        }
                    ],
                },
                "pro": {"default": "gemini-3-pro-preview"},
                "flash": {"default": "gemini-2.5-flash"},
                "flash-lite": {"default": "gemini-2.5-flash-lite"},
            },
        },
    )


def test_visible_display_models_include_only_visible_concrete_models() -> None:
    registry = normalize_registry(_registry_config(), _source())

    assert [model.model_id for model in registry.display_models()] == [
        "gemini-3-pro-preview",
        "gemini-2.5-flash",
    ]


def test_all_models_include_hidden_concrete_models_and_alias_definitions() -> None:
    registry = normalize_registry(_registry_config(), _source())

    models = {
        model.model_id: model for model in registry.display_models(include_all=True)
    }
    aliases = {
        alias.name: alias for alias in registry.display_aliases(include_all=True)
    }

    assert models["gemini-3.1-pro-preview-customtools"].is_concrete is True
    assert models["gemini-3.1-pro-preview-customtools"].is_visible is False
    assert aliases["chat-base"].extends == "base"
    assert aliases["classifier"].target_model == "flash-lite"


def test_standard_aliases_are_visible_with_resolution_rules() -> None:
    registry = normalize_registry(_registry_config(), _source())

    aliases = {alias.name: alias for alias in registry.display_aliases()}

    assert aliases["auto"].is_visible is True
    assert aliases["pro"].is_standard is True
    assert aliases["flash"].is_standard is True
    assert aliases["flash-lite"].resolution == {"default": "gemini-2.5-flash-lite"}
    assert aliases["auto"].resolution == {
        "default": "gemini-3-pro-preview",
        "contexts": [
            {
                "condition": {"hasAccessToPreview": False},
                "target": "gemini-2.5-flash",
            }
        ],
    }


def test_preview_and_feature_flags_are_preserved_in_json_output() -> None:
    registry = normalize_registry(_registry_config(), _source())
    output = registry.to_json()
    first_model = cast(list[JsonObject], output["models"])[0]

    assert first_model["model_id"] == "gemini-3-pro-preview"
    assert first_model["is_preview"] is True
    assert first_model["features"] == {"thinking": True, "multimodalToolUse": True}
    assert output["account_availability"] == {
        "status": "not_checked",
        "note": "CLI registry is local; run probe mode to check account callability.",
    }


def test_probe_model_closes_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

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
            stdout='{"response": "OK"}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = probe_model(Path("/usr/local/bin/gemini"), "gemini-3.1-flash-lite")

    assert result.status == "ok"
    assert result.response_text == "OK"
    assert captured["stdin"] == subprocess.DEVNULL
