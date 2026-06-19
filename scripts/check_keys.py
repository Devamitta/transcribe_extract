"""Preflight text and image provider availability for pipeline wrappers."""

import argparse
import os
from collections.abc import Callable
from typing import Any, Protocol

import requests
from dotenv import load_dotenv

from tools.printer import printer as pr

load_dotenv()

TEXT_PROVIDER_NAMES = {
    "google",
    "gemini-cli",
    "antigravity-cli",
    "agy",
    "deepseek",
    "openrouter",
}
TEXT_PROVIDER_ERROR = (
    "Set PROVIDER=google, PROVIDER=gemini-cli, "
    "PROVIDER=antigravity-cli, PROVIDER=agy, PROVIDER=deepseek, "
    "or PROVIDER=openrouter in .env"
)

IMAGE_PROVIDER_OPENROUTER = "openrouter"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_IMAGE_PREFLIGHT_MODELS = [
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "openai/gpt-oss-120b:free",
    "arcee-ai/trinity-large-preview:free",
    "minimax/minimax-m2.5:free",
]
OPENROUTER_IMAGE_PREFLIGHT_TIMEOUT = 15

KeyCheckFn = Callable[[], bool]


class OpenRouterPostFn(Protocol):
    """Callable shape for the OpenRouter preflight HTTP request."""

    def __call__(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: int,
    ) -> requests.Response: ...


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preflight configured AI provider availability."
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Check the configured text provider from PROVIDER.",
    )
    parser.add_argument(
        "--image",
        action="store_true",
        help="Check OpenRouter availability for the image-generation path.",
    )
    return parser


def _exit_code(exc: SystemExit) -> int:
    return exc.code if isinstance(exc.code, int) else 1


def _safe_error(exc: Exception) -> str:
    return str(exc).splitlines()[0][:200]


def run_text_preflight(check_working_key: KeyCheckFn | None = None) -> int:
    """Check the configured text provider through tools.provider."""
    provider_name = os.getenv("PROVIDER", "google").lower()
    pr.green(f"Text provider: {provider_name}")

    if provider_name not in TEXT_PROVIDER_NAMES:
        pr.red(f"[ERROR] Unknown provider: {provider_name}")
        pr.white(TEXT_PROVIDER_ERROR)
        return 1

    if check_working_key is None:
        try:
            from tools.provider import get_working_key
        except SystemExit as exc:
            pr.red("Text preflight: FAILED")
            return _exit_code(exc)
        except Exception as exc:
            pr.red(f"Text preflight load failed: {_safe_error(exc)}")
            return 1

        check_working_key = get_working_key

    try:
        if check_working_key():
            pr.green("Text preflight: OK")
            return 0
    except Exception as exc:
        pr.red(f"Text preflight failed: {_safe_error(exc)}")
        return 1

    pr.red("Text preflight: FAILED")
    return 1


def _post_openrouter_text_probe(
    api_key: str,
    model: str,
    post_fn: OpenRouterPostFn,
) -> requests.Response:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sasanarakkha.org",
        "X-Title": "DPS Transcriber",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with OK.",
            }
        ],
        "max_tokens": 2,
        "temperature": 0,
    }
    return post_fn(
        OPENROUTER_CHAT_COMPLETIONS_URL,
        headers=headers,
        json=payload,
        timeout=OPENROUTER_IMAGE_PREFLIGHT_TIMEOUT,
    )


def run_image_preflight(
    post_fn: OpenRouterPostFn = requests.post,
) -> int:
    """Check OpenRouter text availability before image generation."""
    image_provider = os.getenv("IMAGE_PROVIDER", IMAGE_PROVIDER_OPENROUTER).lower()
    pr.green(f"Image provider: {image_provider}")

    if image_provider != IMAGE_PROVIDER_OPENROUTER:
        pr.red(f"[ERROR] Unsupported image provider: {image_provider}")
        pr.white("Set IMAGE_PROVIDER=openrouter in .env")
        return 1

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        pr.red("No OPENROUTER_API_KEY found in .env")
        return 1

    last_failure = ""
    for model in OPENROUTER_IMAGE_PREFLIGHT_MODELS:
        pr.white(
            "Checking OpenRouter image path with text model "
            f"{model} (timeout={OPENROUTER_IMAGE_PREFLIGHT_TIMEOUT}s)"
        )
        try:
            response = _post_openrouter_text_probe(api_key, model, post_fn)
        except requests.exceptions.RequestException as exc:
            last_failure = f"{model}: {_safe_error(exc)}"
            pr.amber(f"OpenRouter preflight request failed for {model}")
            continue

        if response.status_code == 200:
            pr.green("Image preflight: OK")
            return 0

        last_failure = f"{model}: HTTP {response.status_code}"
        pr.amber(
            f"OpenRouter preflight failed for {model}: HTTP {response.status_code}"
        )

    pr.red(f"Image preflight: FAILED ({last_failure})")
    return 1


def main(argv: list[str] | None = None) -> int:
    """Run selected provider preflights and return a process exit code."""
    args = _build_parser().parse_args(argv)
    run_text = args.text or not args.image
    run_image = args.image

    status = 0
    if run_text:
        status = max(status, run_text_preflight())
    if run_image:
        status = max(status, run_image_preflight())
    return status


if __name__ == "__main__":
    raise SystemExit(main())
