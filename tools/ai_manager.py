# Cross-provider AI manager routing requests across multiple providers with per-model rate limiting.

from __future__ import annotations

import importlib
import json
import os
import shutil
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

from tools.printer import printer as pr

AI_MODELS_PATH = Path("tools/ai_models.json")

# Providers using CLI_TEST_MODE (--dry-run) for test-model selection; others use TEST_MODE.
_CLI_TEST_MODE_PROVIDERS: frozenset[str] = frozenset({"antigravity-cli"})

# Canonical alias map (normalise before use)
_PROVIDER_ALIASES: dict[str, str] = {"agy": "antigravity-cli"}

# How each provider's get_working_key is called
_KEY_STYLE: dict[str, str] = {
    "google": "single_model",
    "antigravity-cli": "loop_models",
    "deepseek": "no_args",
    "openrouter": "no_args",
}

# Provider name → Python module path
_PROVIDER_MODULE_PATHS: dict[str, str] = {
    "google": "tools.gemini",
    "antigravity-cli": "tools.antigravity_cli",
    "deepseek": "tools.deepseek",
    "openrouter": "tools.openrouter",
}

# Providers whose generate_content accepts a `timeout` kwarg.
# CLI providers (e.g. antigravity-cli) use their own built-in default timeout.
_ACCEPTS_TIMEOUT: frozenset[str] = frozenset({"deepseek", "openrouter"})


class AIResponse(NamedTuple):
    """Response from an AI provider request."""

    content: str | None
    status_message: str


class _ModelEntry(NamedTuple):
    provider: str
    model: str
    delay: float
    timeout: float


def _load_models_from_json() -> tuple[
    list[_ModelEntry],
    list[_ModelEntry],
    list[_ModelEntry],
    dict[str, dict[str, list[str]]],
]:
    """Load default_models, test_models, pro_models, and provider_models from ai_models.json."""
    try:
        data: dict[str, object] = json.loads(AI_MODELS_PATH.read_text(encoding="utf-8"))

        def _to_entry(m: dict[str, object]) -> _ModelEntry:
            return _ModelEntry(
                provider=str(m["provider"]),
                model=str(m["model"]),
                delay=float(m.get("delay", 0)),  # type: ignore[arg-type]
                timeout=float(m.get("timeout", 150.0)),  # type: ignore[arg-type]
            )

        default_models = [
            _to_entry(m)  # type: ignore[arg-type]
            for m in data.get("default_models", [])  # type: ignore[union-attr]
        ]
        test_models = [
            _to_entry(m)  # type: ignore[arg-type]
            for m in data.get("test_models", [])  # type: ignore[union-attr]
        ]
        pro_models = [
            _to_entry(m)  # type: ignore[arg-type]
            for m in data.get("pro_models", [])  # type: ignore[union-attr]
        ]
        provider_models: dict[str, dict[str, list[str]]] = data.get(  # type: ignore[assignment]
            "provider_models", {}
        )
        return default_models, test_models, pro_models, provider_models
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        pr.red(f"Failed to load {AI_MODELS_PATH}: {e}")
        return [], [], [], {}


def _has_gemini_key() -> bool:
    """True if any GEMINI_API_KEY or GEMINI_API_KEY_N is set."""
    if os.getenv("GEMINI_API_KEY"):
        return True
    for i in range(1, 100):
        if os.getenv(f"GEMINI_API_KEY_{i}"):
            return True
    return False


class AIManager:
    """Cross-provider AI manager with per-model rate limiting and background agy probe."""

    _agy_probe_thread: threading.Thread | None = None

    def __init__(self) -> None:
        (
            self._default_models,
            self._test_models,
            self._pro_models,
            (self._provider_models),
        ) = _load_models_from_json()
        self.model_last_request: dict[str, float] = {}

        # Providers registered for the cross-provider default path.
        # openrouter MUST NOT be imported without OPENROUTER_API_KEY (exit(1) at import).
        # gemini MUST NOT be imported without at least one GEMINI_API_KEY (exit(1) at import).
        self._providers: dict[str, ModuleType] = {}

        if os.getenv("DEEPSEEK_API_KEY"):
            self._providers["deepseek"] = importlib.import_module("tools.deepseek")

        if os.getenv("OPENROUTER_API_KEY"):
            self._providers["openrouter"] = importlib.import_module("tools.openrouter")

        if _has_gemini_key():
            self._providers["google"] = importlib.import_module("tools.gemini")

        # agy: check PATH without blocking; confirm via background probe.
        if shutil.which("agy"):
            self._agy_probe_thread = threading.Thread(
                target=self._probe_agy,
                name="agy-probe",
                daemon=True,
            )
            self._agy_probe_thread.start()

    def _probe_agy(self) -> None:
        """Confirm agy works off-thread; register only after probe succeeds."""
        try:
            from tools.antigravity_cli import get_working_key

            if get_working_key():
                self._providers["antigravity-cli"] = importlib.import_module(
                    "tools.antigravity_cli"
                )
        except Exception:  # noqa: BLE001
            pass

    def _wait_for_agy(self) -> None:
        """Block until the background agy probe finishes (forced-antigravity requests)."""
        thread = self._agy_probe_thread
        if thread is not None and thread.is_alive():
            thread.join()

    def _normalize(self, provider: str) -> str:
        return _PROVIDER_ALIASES.get(provider, provider)

    def _lazy_import(self, provider: str) -> ModuleType | None:
        """Import a provider module on demand. Never imports openrouter without its key."""
        if provider == "openrouter" and not os.getenv("OPENROUTER_API_KEY"):
            return None
        if provider == "google" and not _has_gemini_key():
            return None
        module_path = _PROVIDER_MODULE_PATHS.get(provider)
        if module_path is None:
            return None
        return importlib.import_module(module_path)

    def _provider_timeout(self, provider: str) -> float:
        """Timeout for a provider from JSON model lists, defaulting to 150s."""
        for entry in self._default_models + self._test_models:
            if entry.provider == provider:
                return entry.timeout
        return 150.0

    def _get_provider_models(
        self, provider: str, test_mode: bool, cli_test_mode: bool
    ) -> list[_ModelEntry]:
        """Ordered model list for a single-provider path."""
        pm = self._provider_models.get(provider, {})
        in_test = cli_test_mode if provider in _CLI_TEST_MODE_PROVIDERS else test_mode
        model_names: list[str] = pm.get("test" if in_test else "work", [])
        timeout = self._provider_timeout(provider)
        return [_ModelEntry(provider, name, 0.0, timeout) for name in model_names]

    def _active_default_models(self, test_mode: bool) -> list[_ModelEntry]:
        return self._test_models if test_mode else self._default_models

    def _enforce_rate_limit(self, provider: str, model: str, delay: float) -> None:
        key = f"{provider}:{model}"
        elapsed = time.monotonic() - self.model_last_request.get(key, 0.0)
        wait = delay - elapsed
        if wait > 0:
            pr.green(f"RATE LIMITING {key} — waiting {wait:.2f}s")
            time.sleep(wait)
        self.model_last_request[key] = time.monotonic()

    def is_provider_working(
        self, provider: str, test_mode: bool, cli_test_mode: bool
    ) -> bool:
        """Check availability for a specific provider (single-provider override path)."""
        norm = self._normalize(provider)

        if norm == "antigravity-cli":
            self._wait_for_agy()

        module = self._lazy_import(norm)
        if module is None:
            return False

        key_style = _KEY_STYLE.get(norm, "no_args")
        models = self._get_provider_models(norm, test_mode, cli_test_mode)

        if key_style == "no_args":
            return bool(module.get_working_key())
        if key_style == "single_model":
            if not models:
                return False
            return bool(module.get_working_key(models[0].model))
        # loop_models
        for entry in models:
            try:
                if module.get_working_key(entry.model):
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def is_any_available(self, test_mode: bool) -> bool:
        """True if ≥1 provider in the active default list is registered."""
        return any(
            e.provider in self._providers
            for e in self._active_default_models(test_mode)
        )

    def _generate_with_models(
        self,
        models: list[_ModelEntry],
        contents: str,
        system_instruction: str,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
    ) -> AIResponse:
        """Walk a model list, falling through on failure. Returns AIResponse."""
        errors: list[str] = []

        for entry in models:
            provider = entry.provider
            module = self._providers.get(provider) or self._lazy_import(provider)
            if module is None:
                continue

            self._enforce_rate_limit(provider, entry.model, entry.delay)

            start = time.monotonic()
            pr.green(f"REQUEST {provider} - {entry.model}")

            try:
                kwargs: dict[str, object] = {
                    "contents": contents,
                    "system_instruction": system_instruction,
                    "model": entry.model,
                    "max_output_tokens": max_output_tokens,
                    "temperature": temperature,
                }
                if provider in _ACCEPTS_TIMEOUT:
                    kwargs["timeout"] = int(entry.timeout)

                result: str = module.generate_content(**kwargs)  # type: ignore[attr-defined]
                duration = time.monotonic() - start
                status = f"SUCCESS in {duration:.2f}s. {provider}/{entry.model}"
                if errors:
                    status += f" (after {len(errors)} failed: {' | '.join(errors)})"
                pr.green(status)
                return AIResponse(content=result, status_message=status)
            except Exception as e:  # noqa: BLE001
                duration = time.monotonic() - start
                err = f"{provider}/{entry.model} ERROR in {duration:.2f}s: {e}"
                pr.red(err)
                errors.append(err)

        final = "All AI providers failed." + (
            " " + " | ".join(errors) if errors else ""
        )
        pr.red(final)
        return AIResponse(content=None, status_message=final)

    def request(
        self,
        contents: str,
        system_instruction: str,
        provider_preference: str | None = None,
        model: str | None = None,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
        test_mode: bool = False,
        cli_test_mode: bool = False,
        active_provider: str | None = None,
    ) -> AIResponse:
        """Make a request, walking the model list and falling through on failure.

        Priority: explicit (provider_preference, model) > PROVIDER single-override >
        cross-provider default_models.
        Never raises for provider failures; returns AIResponse(None, ...) on total failure.
        """
        if provider_preference and model:
            norm_pref = self._normalize(provider_preference)
            if norm_pref == "antigravity-cli":
                self._wait_for_agy()
            timeout = self._provider_timeout(norm_pref)
            models_to_try = [_ModelEntry(norm_pref, model, 0.0, timeout)]
        elif (
            active_provider
            and self._normalize(active_provider) in _PROVIDER_MODULE_PATHS
        ):
            norm_prov = self._normalize(active_provider)
            models_to_try = self._get_provider_models(
                norm_prov, test_mode, cli_test_mode
            )
        else:
            models_to_try = self._active_default_models(test_mode)

        return self._generate_with_models(
            models_to_try,
            contents,
            system_instruction,
            max_output_tokens,
            temperature,
        )

    def generate_pro(
        self,
        contents: str,
        system_instruction: str,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
    ) -> AIResponse:
        """Make a request using the pro model list. Never raises."""
        return self._generate_with_models(
            self._pro_models,
            contents,
            system_instruction,
            max_output_tokens,
            temperature,
        )
