"""Network-free tests for AIManager cross-provider routing and rate limiting."""

from __future__ import annotations

import sys
import time
from types import ModuleType

import pytest

from tools.ai_manager import AIManager, AIResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_module(
    name: str,
    *,
    generate_ok: bool = True,
    generate_result: str = "ok",
    key_ok: bool = True,
) -> ModuleType:
    """Build a minimal fake provider module. Accepts optional timeout kwarg."""
    mod = ModuleType(name)

    def generate_content(
        contents: str,
        system_instruction: str,
        model: str,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
        timeout: int = 30,
    ) -> str:
        if not generate_ok:
            raise RuntimeError(f"{name} generate failed")
        return generate_result

    def get_working_key() -> bool:  # no-args style
        return key_ok

    mod.generate_content = generate_content  # type: ignore[attr-defined]
    mod.get_working_key = get_working_key  # type: ignore[attr-defined]
    return mod


def _fake_loop_module(
    name: str,
    key_results: dict[str, bool],
    generate_failures: set[str],
    generate_result: str = "loop-ok",
) -> tuple[ModuleType, list[str], list[str]]:
    """Fake module for providers that use loop_models key style."""
    mod = ModuleType(name)
    checked: list[str] = []
    generated: list[str] = []

    def get_working_key(model: str) -> bool:
        checked.append(model)
        return key_results.get(model, False)

    def generate_content(
        contents: str,
        system_instruction: str,
        model: str,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
        timeout: int = 30,
    ) -> str:
        generated.append(model)
        if model in generate_failures:
            raise RuntimeError(f"{model} failed")
        return generate_result

    mod.get_working_key = get_working_key  # type: ignore[attr-defined]
    mod.generate_content = generate_content  # type: ignore[attr-defined]
    return mod, checked, generated


def _manager_with_providers(providers: dict[str, ModuleType]) -> AIManager:
    """Return an AIManager with pre-populated _providers (no real init)."""
    m = AIManager.__new__(AIManager)
    from tools.ai_manager import _load_models_from_json

    m._default_models, m._test_models, m._provider_models = _load_models_from_json()
    m._providers = dict(providers)
    m.model_last_request = {}
    m._agy_probe_thread = None
    return m


# ---------------------------------------------------------------------------
# Cross-provider fallback tests
# ---------------------------------------------------------------------------


class TestCrossProviderFallback:
    def test_primary_succeeds_returns_content(self) -> None:
        agy_mod = _fake_module("antigravity-cli", generate_result="agy-response")
        mgr = _manager_with_providers({"antigravity-cli": agy_mod})

        resp = mgr.request("prompt", "system")

        assert resp.content == "agy-response"
        assert "SUCCESS" in resp.status_message

    def test_primary_fails_falls_through_to_deepseek(self) -> None:
        agy_mod = _fake_module("antigravity-cli", generate_ok=False)
        ds_mod = _fake_module("deepseek", generate_result="deepseek-response")
        mgr = _manager_with_providers({"antigravity-cli": agy_mod, "deepseek": ds_mod})

        resp = mgr.request("prompt", "system")

        assert resp.content == "deepseek-response"
        assert "SUCCESS" in resp.status_message
        assert "failed" in resp.status_message  # mentions prior failure

    def test_agy_and_deepseek_fail_falls_through_to_openrouter(self) -> None:
        mgr = _manager_with_providers(
            {
                "antigravity-cli": _fake_module("antigravity-cli", generate_ok=False),
                "deepseek": _fake_module("deepseek", generate_ok=False),
                "openrouter": _fake_module("openrouter", generate_result="or-response"),
            }
        )

        resp = mgr.request("prompt", "system")

        assert resp.content == "or-response"

    def test_total_failure_returns_none_content(self) -> None:
        mgr = _manager_with_providers(
            {
                "antigravity-cli": _fake_module("antigravity-cli", generate_ok=False),
                "deepseek": _fake_module("deepseek", generate_ok=False),
                "openrouter": _fake_module("openrouter", generate_ok=False),
            }
        )

        resp = mgr.request("prompt", "system")

        assert resp.content is None
        assert "All AI providers failed" in resp.status_message

    def test_total_failure_does_not_raise(self) -> None:
        mgr = _manager_with_providers(
            {"deepseek": _fake_module("deepseek", generate_ok=False)}
        )

        resp = mgr.request("prompt", "system")  # must not raise

        assert resp.content is None

    def test_unavailable_provider_skipped_in_default_path(self) -> None:
        # Only deepseek is registered; antigravity-cli (first in default list) is absent.
        ds_mod = _fake_module("deepseek", generate_result="ds")
        mgr = _manager_with_providers({"deepseek": ds_mod})

        resp = mgr.request("prompt", "system")

        assert resp.content == "ds"


# ---------------------------------------------------------------------------
# PROVIDER single-override tests
# ---------------------------------------------------------------------------


class TestProviderOverride:
    def test_provider_openrouter_restricts_to_openrouter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PROVIDER=openrouter must only use openrouter (test_yt_ardmk requirement)."""
        or_mod = _fake_module("openrouter", generate_result="or-only")
        monkeypatch.setitem(sys.modules, "tools.openrouter", or_mod)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        mgr = _manager_with_providers({})  # nothing registered in default list

        resp = mgr.request(
            "prompt", "system", active_provider="openrouter", test_mode=False
        )

        assert resp.content == "or-only"

    def test_provider_deepseek_uses_deepseek_work_models(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ds_mod, _, generated = _fake_loop_module(
            "tools.deepseek",
            key_results={},
            generate_failures=set(),
            generate_result="ds-work",
        )
        # deepseek's get_working_key takes no args — override with a simple bool fn
        ds_mod.get_working_key = lambda: True  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "tools.deepseek", ds_mod)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        mgr = _manager_with_providers({})

        resp = mgr.request(
            "prompt", "system", active_provider="deepseek", test_mode=False
        )

        assert resp.content == "ds-work"
        assert "deepseek-v4-flash" in generated

    def test_agy_alias_maps_to_antigravity_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agy_mod = _fake_module("tools.antigravity_cli", generate_result="agy-via-alias")
        monkeypatch.setitem(sys.modules, "tools.antigravity_cli", agy_mod)
        mgr = _manager_with_providers({})

        resp = mgr.request("prompt", "system", active_provider="agy")

        assert resp.content == "agy-via-alias"


# ---------------------------------------------------------------------------
# TEST_MODE model selection
# ---------------------------------------------------------------------------


class TestTestModeModelSelection:
    def test_test_mode_uses_test_models(self) -> None:
        """test_mode=True should route to test_models (deepseek in JSON)."""
        ds_mod = _fake_module("deepseek", generate_result="test-response")
        mgr = _manager_with_providers({"deepseek": ds_mod})

        resp = mgr.request("prompt", "system", test_mode=True)

        assert resp.content == "test-response"

    def test_work_mode_uses_default_models(self) -> None:
        agy_mod = _fake_module("antigravity-cli", generate_result="agy-work")
        mgr = _manager_with_providers({"antigravity-cli": agy_mod})

        resp = mgr.request("prompt", "system", test_mode=False)

        assert resp.content == "agy-work"


# ---------------------------------------------------------------------------
# Per-model delay / rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_delay_enforced_between_calls(self) -> None:
        ds_mod = _fake_module("deepseek", generate_result="r")
        mgr = _manager_with_providers({"deepseek": ds_mod})
        delay_seconds = 0.1

        # Patch default_models to use a model with a small delay
        from tools.ai_manager import _ModelEntry

        mgr._default_models = [
            _ModelEntry("deepseek", "deepseek-v4-flash", delay_seconds, 60.0)
        ]

        # First call – no wait
        mgr.request("p", "s", test_mode=False)
        t0 = time.monotonic()
        # Second call – must wait ≥ delay
        mgr.request("p", "s", test_mode=False)
        elapsed = time.monotonic() - t0

        assert elapsed >= delay_seconds * 0.8  # allow 20% slack

    def test_zero_delay_does_not_sleep(self) -> None:
        ds_mod = _fake_module("deepseek", generate_result="r")
        mgr = _manager_with_providers({"deepseek": ds_mod})

        t0 = time.monotonic()
        mgr.request("p", "s", test_mode=False)
        mgr.request("p", "s", test_mode=False)
        elapsed = time.monotonic() - t0

        assert elapsed < 0.5  # two zero-delay calls must be fast


# ---------------------------------------------------------------------------
# Explicit provider_preference + model
# ---------------------------------------------------------------------------


class TestExplicitPreference:
    def test_explicit_provider_model_bypasses_default_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        or_mod = _fake_module("openrouter", generate_result="explicit")
        monkeypatch.setitem(sys.modules, "tools.openrouter", or_mod)
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        mgr = _manager_with_providers({})

        resp = mgr.request(
            "p",
            "s",
            provider_preference="openrouter",
            model="some/model",
        )

        assert resp.content == "explicit"

    def test_explicit_provider_model_required_together(self) -> None:
        """provider_preference without model falls through to default list."""
        ds_mod = _fake_module("deepseek", generate_result="default-ds")
        # Default path uses _providers directly (not lazy_import)
        mgr = _manager_with_providers({"deepseek": ds_mod})

        # No model → not treated as explicit, uses default list
        resp = mgr.request(
            "p",
            "s",
            provider_preference="openrouter",
            # model omitted
        )

        # Should use default path; deepseek is the first available in default_models
        assert resp.content == "default-ds"


# ---------------------------------------------------------------------------
# is_provider_working tests
# ---------------------------------------------------------------------------


class TestIsProviderWorking:
    def test_no_args_style_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ds_mod = _fake_module("deepseek", key_ok=True)
        monkeypatch.setitem(sys.modules, "tools.deepseek", ds_mod)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "key")
        mgr = _manager_with_providers({})

        assert mgr.is_provider_working("deepseek", False, False) is True

    def test_loop_models_style_antigravity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mgr = _manager_with_providers({})
        # Derive the first work model from ai_models.json (single source of truth).
        first_model = mgr._provider_models["antigravity-cli"]["work"][0]
        agy_mod, checked, _ = _fake_loop_module(
            "tools.antigravity_cli",
            key_results={first_model: True},
            generate_failures=set(),
        )
        monkeypatch.setitem(sys.modules, "tools.antigravity_cli", agy_mod)

        result = mgr.is_provider_working("antigravity-cli", False, False)

        assert result is True
        assert checked == [first_model]

    def test_unavailable_provider_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No openrouter key → lazy_import returns None
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        mgr = _manager_with_providers({})

        assert mgr.is_provider_working("openrouter", False, False) is False

    def test_is_any_available_true_when_provider_registered(self) -> None:
        ds_mod = _fake_module("deepseek")
        mgr = _manager_with_providers({"deepseek": ds_mod})

        assert mgr.is_any_available(test_mode=False) is True

    def test_is_any_available_false_when_none_registered(self) -> None:
        mgr = _manager_with_providers({})

        assert mgr.is_any_available(test_mode=False) is False


# ---------------------------------------------------------------------------
# AIResponse shape
# ---------------------------------------------------------------------------


class TestAIResponse:
    def test_airesponse_is_named_tuple(self) -> None:
        r = AIResponse(content="hi", status_message="ok")
        assert r.content == "hi"
        assert r.status_message == "ok"

    def test_airesponse_none_content_allowed(self) -> None:
        r = AIResponse(content=None, status_message="failed")
        assert r.content is None
