"""Tests for model and image provider preflight behavior."""

from typing import Any

import pytest
import requests

from scripts import check_keys


class DummyPrinter:
    """Capture preflight log messages without writing project log files."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def green(self, message: str) -> None:
        self.messages.append(message)

    def red(self, message: str) -> None:
        self.messages.append(message)

    def white(self, message: str) -> None:
        self.messages.append(message)

    def amber(self, message: str) -> None:
        self.messages.append(message)


@pytest.fixture()
def printer(monkeypatch: pytest.MonkeyPatch) -> DummyPrinter:
    dummy = DummyPrinter()
    monkeypatch.setattr(check_keys, "pr", dummy)
    return dummy


def _response(status_code: int) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    return response


def test_text_preflight_success_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    printer: DummyPrinter,
) -> None:
    monkeypatch.setenv("PROVIDER", "google")

    result = check_keys.run_text_preflight(lambda: True)

    assert result == 0
    assert "Text preflight: OK" in printer.messages


def test_text_preflight_failure_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    printer: DummyPrinter,
) -> None:
    monkeypatch.setenv("PROVIDER", "openrouter")

    result = check_keys.run_text_preflight(lambda: False)

    assert result == 1
    assert "Text preflight: FAILED" in printer.messages


def test_text_preflight_unknown_provider_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    printer: DummyPrinter,
) -> None:
    monkeypatch.setenv("PROVIDER", "unknown")

    result = check_keys.run_text_preflight(lambda: True)

    assert result == 1
    assert "[ERROR] Unknown provider: unknown" in printer.messages


def test_image_preflight_missing_openrouter_key_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    printer: DummyPrinter,
) -> None:
    monkeypatch.setenv("IMAGE_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = check_keys.run_image_preflight()

    assert result == 1
    assert "No OPENROUTER_API_KEY found in .env" in printer.messages


def test_image_preflight_unsupported_provider_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    printer: DummyPrinter,
) -> None:
    monkeypatch.setenv("IMAGE_PROVIDER", "other")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-token")

    result = check_keys.run_image_preflight()

    assert result == 1
    assert "[ERROR] Unsupported image provider: other" in printer.messages


def test_image_preflight_failed_openrouter_request_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    printer: DummyPrinter,
) -> None:
    calls: list[str] = []
    monkeypatch.setenv("IMAGE_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-token")

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: int,
    ) -> requests.Response:
        calls.append(json["model"])
        assert url == check_keys.OPENROUTER_CHAT_COMPLETIONS_URL
        assert headers["Authorization"] == "Bearer secret-token"
        assert timeout == check_keys.OPENROUTER_IMAGE_PREFLIGHT_TIMEOUT
        return _response(500)

    result = check_keys.run_image_preflight(fake_post)

    assert result == 1
    assert calls == check_keys.OPENROUTER_IMAGE_PREFLIGHT_MODELS
    assert printer.messages[-1].startswith("Image preflight: FAILED")
    assert all("secret-token" not in message for message in printer.messages)


def test_image_preflight_success_returns_zero_without_leaking_key(
    monkeypatch: pytest.MonkeyPatch,
    printer: DummyPrinter,
) -> None:
    captured_models: list[str] = []
    monkeypatch.setenv("IMAGE_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-token")

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: int,
    ) -> requests.Response:
        captured_models.append(json["model"])
        return _response(200)

    result = check_keys.run_image_preflight(fake_post)

    assert result == 0
    assert captured_models == [check_keys.OPENROUTER_IMAGE_PREFLIGHT_MODELS[0]]
    assert "Image preflight: OK" in printer.messages
    assert all("secret-token" not in message for message in printer.messages)


def test_main_defaults_to_text_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"text": 0, "image": 0}

    def fake_text(check_working_key: check_keys.KeyCheckFn | None = None) -> int:
        calls["text"] += 1
        return 0

    def fake_image(post_fn: check_keys.OpenRouterPostFn = requests.post) -> int:
        calls["image"] += 1
        return 0

    monkeypatch.setattr(check_keys, "run_text_preflight", fake_text)
    monkeypatch.setattr(check_keys, "run_image_preflight", fake_image)

    result = check_keys.main([])

    assert result == 0
    assert calls == {"text": 1, "image": 0}


def test_main_image_flag_runs_image_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"text": 0, "image": 0}

    def fake_text(check_working_key: check_keys.KeyCheckFn | None = None) -> int:
        calls["text"] += 1
        return 0

    def fake_image(post_fn: check_keys.OpenRouterPostFn = requests.post) -> int:
        calls["image"] += 1
        return 0

    monkeypatch.setattr(check_keys, "run_text_preflight", fake_text)
    monkeypatch.setattr(check_keys, "run_image_preflight", fake_image)

    result = check_keys.main(["--image"])

    assert result == 0
    assert calls == {"text": 0, "image": 1}
