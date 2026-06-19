# Thin shim over AIManager — preserves the public provider API for all scripts.

import concurrent.futures
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv  # type: ignore[import-untyped]

# Provider-routing policy comes ONLY from the real process environment (e.g.
# `PROVIDER=agy uv run ...` on the command line), never from a persistent pin in .env.
# Capture the real-env value before loading .env so a stale `PROVIDER=` line in .env
# cannot disable the cross-provider default_models chain.
_real_provider = os.environ.get("PROVIDER")

load_dotenv()

# Unset (or .env-only) PROVIDER → cross-provider fallback chain (default_models in
# ai_models.json). A real-env PROVIDER restricts routing to that single provider.
PROVIDER = (_real_provider or "").lower()
TEST_MODE = "--test" in sys.argv or "-t" in sys.argv
CLI_TEST_MODE = TEST_MODE or "--dry-run" in sys.argv

CACHE_PREFIX = (
    "The task instructions are provided separately and remain constant across requests.\n"
    "Treat everything after `SOURCE_TEXT:` as the unique input for this request.\n\n"
    "SOURCE_TEXT:\n"
)

PROVIDER_ERROR_MSG = (
    "Set PROVIDER=google, PROVIDER=antigravity-cli, "
    "PROVIDER=agy, PROVIDER=openrouter, or PROVIDER=deepseek in .env"
)

_KNOWN_PROVIDERS = {
    "google",
    "antigravity-cli",
    "agy",
    "deepseek",
    "openrouter",
}


def build_cacheable_contents(unique_text: str) -> str:
    """Prefix unique request text with a stable cache-friendly header."""
    return f"{CACHE_PREFIX}{unique_text}"


# ---------------------------------------------------------------------------
# Model-list constants — read from ai_models.json so JSON is the single source
# of truth, while existing tests that access these attributes stay green.
# ---------------------------------------------------------------------------

_AI_MODELS_PATH = Path("tools/ai_models.json")

try:
    _json_data: dict[str, object] = json.loads(
        _AI_MODELS_PATH.read_text(encoding="utf-8")
    )
    _pm: dict[str, dict[str, list[str]]] = _json_data.get(  # type: ignore[assignment]
        "provider_models", {}
    )
except (FileNotFoundError, json.JSONDecodeError):
    _pm = {}

GEMINI_WORK_MODELS: list[str] = _pm.get("google", {}).get("work", ["gemini-2.5-flash"])
GEMINI_TEST_MODELS: list[str] = _pm.get("google", {}).get(
    "test", ["gemini-3.1-flash-lite-preview"]
)
ANTIGRAVITY_CLI_WORK_MODELS: list[str] = _pm.get("antigravity-cli", {}).get("work", [])
ANTIGRAVITY_CLI_TEST_MODELS: list[str] = _pm.get("antigravity-cli", {}).get("test", [])

# ---------------------------------------------------------------------------
# Lazy AIManager singleton
# ---------------------------------------------------------------------------

from tools.ai_manager import AIManager, AIResponse  # noqa: E402

_manager: AIManager | None = None


def _get_manager() -> AIManager:
    global _manager
    if _manager is None:
        _manager = AIManager()
    return _manager


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_content(
    contents: str,
    system_instruction: str,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
) -> str:
    """Generate content; raises Exception(status_message) on total provider failure."""
    active = PROVIDER if PROVIDER in _KNOWN_PROVIDERS else None
    response: AIResponse = _get_manager().request(
        contents=contents,
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        test_mode=TEST_MODE,
        cli_test_mode=CLI_TEST_MODE,
        active_provider=active,
    )
    if response.content is None:
        raise Exception(response.status_message)
    return response.content


def get_working_key() -> bool:
    """True if ≥1 provider is available for the currently active list."""
    if PROVIDER in _KNOWN_PROVIDERS:
        return _get_manager().is_provider_working(PROVIDER, TEST_MODE, CLI_TEST_MODE)
    return _get_manager().is_any_available(TEST_MODE)


def generate_with_timeout(
    contents: str,
    system_instruction: str,
    timeout: int = 120,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
) -> str:
    """Hard-timeout wrapper around generate_content (default 120s).

    Raises concurrent.futures.TimeoutError if the call exceeds the limit.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        generate_content,
        contents=contents,
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    try:
        return future.result(timeout=timeout)
    finally:
        executor.shutdown(wait=False)
