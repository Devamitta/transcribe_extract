"""Tests OpenRouter image generation request logging and timeout behavior."""

import base64
from typing import Any

import pytest

from tools import image_gen


class DummyPrinter:
    """Capture image generation log messages."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def white(self, message: str) -> None:
        self.messages.append(message)


class FakeImageResponse:
    """Minimal response object for OpenRouter image payload tests."""

    status_code = 200
    text = ""

    def __init__(self, image_bytes: bytes) -> None:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        self._data: dict[str, Any] = {
            "choices": [
                {
                    "message": {
                        "images": [
                            {
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded}",
                                }
                            }
                        ]
                    }
                }
            ]
        }

    def json(self) -> dict[str, Any]:
        return self._data


def test_generate_image_logs_openrouter_model_and_uses_timeout(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_bytes = b"fake jpeg"
    output_path = tmp_path / "thumbnail.jpg"
    captured: dict[str, Any] = {}
    printer = DummyPrinter()

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: int,
    ) -> FakeImageResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeImageResponse(image_bytes)

    monkeypatch.setattr(image_gen, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(image_gen, "pr", printer)
    monkeypatch.setattr(image_gen.requests, "post", fake_post)

    image_gen.generate_image("A forest scene.", output_path)

    assert output_path.read_bytes() == image_bytes
    assert captured["timeout"] == image_gen.OPENROUTER_IMAGE_TIMEOUT
    assert captured["json"]["model"] == image_gen.OPENROUTER_IMAGE_MODEL
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert (
        "  -> openrouter image "
        f"{image_gen.OPENROUTER_IMAGE_MODEL} "
        f"(timeout={image_gen.OPENROUTER_IMAGE_TIMEOUT}s)..."
    ) in printer.messages
