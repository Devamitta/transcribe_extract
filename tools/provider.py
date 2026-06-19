# Unified API provider abstraction that routes requests to either Gemini or OpenRouter based on configuration.

import concurrent.futures
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv  # type: ignore[import-untyped]

load_dotenv()

PROVIDER = os.getenv("PROVIDER", "google").lower()
TEST_MODE = "--test" in sys.argv or "-t" in sys.argv
CLI_TEST_MODE = TEST_MODE or "--dry-run" in sys.argv

CACHE_PREFIX = (
    "The task instructions are provided separately and remain constant across requests.\n"
    "Treat everything after `SOURCE_TEXT:` as the unique input for this request.\n\n"
    "SOURCE_TEXT:\n"
)

PROVIDER_ERROR_MSG = (
    "Set PROVIDER=google, PROVIDER=gemini-cli, PROVIDER=antigravity-cli, "
    "PROVIDER=agy, PROVIDER=openrouter, or PROVIDER=deepseek in .env"
)


def build_cacheable_contents(unique_text: str) -> str:
    """Prefix unique request text with a stable cache-friendly header."""
    return f"{CACHE_PREFIX}{unique_text}"


GEMINI_WORK_MODELS = ["gemini-2.5-flash"]
GEMINI_TEST_MODELS = ["gemini-3.1-flash-lite-preview"]

GEMINI_CLI_WORK_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
]
GEMINI_CLI_TEST_MODELS = ["gemini-3.1-flash-lite"]

ANTIGRAVITY_CLI_WORK_MODELS = [
    "Gemini 3.5 Flash (High)",
    "Gemini 3.1 Pro (Low)",
]
ANTIGRAVITY_CLI_TEST_MODELS = ["Gemini 3.5 Flash (Low)"]

OPENROUTER_WORK_MODELS = [
    "deepseek/deepseek-v4-flash",
    "qwen/qwen-2.5-72b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
]
OPENROUTER_TEST_MODELS = [
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "openai/gpt-oss-120b:free",
    "arcee-ai/trinity-large-preview:free",
    "minimax/minimax-m2.5:free",
]

DEEPSEEK_WORK_MODELS = ["deepseek-v4-flash"]
DEEPSEEK_TEST_MODELS = ["deepseek-v4-flash"]

GenerateFn = Callable[..., str]
KeyCheckFn = Callable[..., bool]


def _load_deepseek() -> tuple[GenerateFn, KeyCheckFn]:
    from tools.deepseek import generate_content, get_working_key

    return generate_content, get_working_key


def _load_openrouter() -> tuple[GenerateFn, KeyCheckFn]:
    from tools.openrouter import generate_content, get_working_key

    return generate_content, get_working_key


def _load_gemini() -> tuple[GenerateFn, KeyCheckFn]:
    from tools.gemini import generate_content, get_working_key

    return generate_content, get_working_key


def _load_gemini_cli() -> tuple[GenerateFn, KeyCheckFn]:
    from tools.gemini_cli import generate_content, get_working_key

    return generate_content, get_working_key


def _load_antigravity_cli() -> tuple[GenerateFn, KeyCheckFn]:
    from tools.antigravity_cli import generate_content, get_working_key

    return generate_content, get_working_key


@dataclass(frozen=True)
class ProviderSpec:
    """Per-provider configuration: lazy module loader plus dispatch deltas."""

    label: str
    loader: Callable[[], tuple[GenerateFn, KeyCheckFn]]
    work_models: list[str]
    test_models: list[str]
    timeout: int | None
    use_cli_test_mode: bool
    key_check_style: Literal["no_args", "single_model", "loop_models"]


@dataclass(frozen=True)
class LoadedProvider:
    """Loaded provider functions with configured fallback behavior."""

    spec: ProviderSpec
    generate_content: Callable[..., str]
    get_working_key: Callable[[], bool]


PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "deepseek": ProviderSpec(
        label="DeepSeek",
        loader=_load_deepseek,
        work_models=DEEPSEEK_WORK_MODELS,
        test_models=DEEPSEEK_TEST_MODELS,
        timeout=30,
        use_cli_test_mode=False,
        key_check_style="no_args",
    ),
    "openrouter": ProviderSpec(
        label="OpenRouter",
        loader=_load_openrouter,
        work_models=OPENROUTER_WORK_MODELS,
        test_models=OPENROUTER_TEST_MODELS,
        # Use 15s timeout as requested by user
        timeout=15,
        use_cli_test_mode=False,
        key_check_style="no_args",
    ),
    "google": ProviderSpec(
        label="Gemini",
        loader=_load_gemini,
        work_models=GEMINI_WORK_MODELS,
        test_models=GEMINI_TEST_MODELS,
        timeout=None,
        use_cli_test_mode=False,
        key_check_style="single_model",
    ),
    "gemini-cli": ProviderSpec(
        label="Gemini CLI",
        loader=_load_gemini_cli,
        work_models=GEMINI_CLI_WORK_MODELS,
        test_models=GEMINI_CLI_TEST_MODELS,
        timeout=None,
        use_cli_test_mode=True,
        key_check_style="loop_models",
    ),
    "antigravity-cli": ProviderSpec(
        label="Antigravity CLI",
        loader=_load_antigravity_cli,
        work_models=ANTIGRAVITY_CLI_WORK_MODELS,
        test_models=ANTIGRAVITY_CLI_TEST_MODELS,
        timeout=None,
        use_cli_test_mode=True,
        key_check_style="loop_models",
    ),
}
PROVIDER_REGISTRY["agy"] = PROVIDER_REGISTRY["antigravity-cli"]
_loaded_provider: LoadedProvider | None = None


def _provider_spec() -> ProviderSpec:
    spec = PROVIDER_REGISTRY.get(PROVIDER)
    if spec is None:
        print(f"[ERROR] Unknown provider: {PROVIDER}")
        print(PROVIDER_ERROR_MSG)
        raise SystemExit(1)
    return spec


def _active_models(spec: ProviderSpec) -> list[str]:
    in_test = CLI_TEST_MODE if spec.use_cli_test_mode else TEST_MODE
    return spec.test_models if in_test else spec.work_models


def _make_generate_content(
    spec: ProviderSpec, generate_fn: GenerateFn
) -> Callable[..., str]:
    def _generate_with_fallback(
        contents: str,
        system_instruction: str,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
    ) -> str:
        extra: dict[str, int] = {}
        if spec.timeout is not None:
            extra["timeout"] = spec.timeout
        for model in _active_models(spec):
            try:
                return generate_fn(
                    contents=contents,
                    system_instruction=system_instruction,
                    model=model,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    **extra,
                )
            except Exception as e:
                print(
                    f"{spec.label} model {model} failed: {e}, trying next...",
                    flush=True,
                )
        raise Exception(f"All {spec.label} models failed")

    return _generate_with_fallback


def _make_get_working_key(spec: ProviderSpec, key_fn: KeyCheckFn) -> Callable[[], bool]:
    def _get_working_key() -> bool:
        if spec.key_check_style == "no_args":
            return key_fn()
        if spec.key_check_style == "single_model":
            return key_fn(_active_models(spec)[0])
        for model in _active_models(spec):
            try:
                if key_fn(model):
                    return True
            except Exception as e:
                print(
                    f"{spec.label} model {model} key check failed: {e}, trying next...",
                    flush=True,
                )
        return False

    return _get_working_key


def _load_provider() -> LoadedProvider:
    global _loaded_provider

    if _loaded_provider is not None:
        return _loaded_provider

    spec = _provider_spec()
    provider_generate, provider_key_check = spec.loader()
    _loaded_provider = LoadedProvider(
        spec=spec,
        generate_content=_make_generate_content(spec, provider_generate),
        get_working_key=_make_get_working_key(spec, provider_key_check),
    )
    return _loaded_provider


def generate_content(
    contents: str,
    system_instruction: str,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
) -> str:
    """Generate content with the configured provider."""
    return _load_provider().generate_content(
        contents=contents,
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def get_working_key() -> bool:
    """Check whether the configured provider is available."""
    return _load_provider().get_working_key()


def generate_with_timeout(
    contents: str,
    system_instruction: str,
    timeout: int = 120,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
) -> str:
    """Wraps generate_content with a hard timeout (default 120s).

    Raises concurrent.futures.TimeoutError if the call exceeds the limit.
    Callers should catch TimeoutError and skip or retry the item.
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
        # wait=False so a hung network thread doesn't block the caller after timeout
        executor.shutdown(wait=False)
