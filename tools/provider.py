# Unified API provider abstraction that routes requests to either Gemini or OpenRouter based on configuration.

import os
import sys

from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("PROVIDER", "google").lower()
TEST_MODE = "--test" in sys.argv or "-t" in sys.argv

GEMINI_WORK_MODELS = ["gemini-2.5-flash"]
GEMINI_TEST_MODELS = ["gemini-3.1-flash-lite-preview"]

OPENROUTER_WORK_MODELS = [
    "deepseek/deepseek-v3.2",
    "qwen/qwen-2.5-72b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
]
OPENROUTER_TEST_MODELS = [
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "openai/gpt-oss-120b:free",
    "arcee-ai/trinity-large-preview:free",
    "minimax/minimax-m2.5:free",
]

if PROVIDER == "openrouter":
    from tools.openrouter import (
        generate_content as or_generate_content,
    )
    from tools.openrouter import (
        get_working_key as or_get_working_key,
    )

    def get_working_key() -> bool:
        return or_get_working_key()

    def _wrap_generate_content(
        contents: str,
        system_instruction: str,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
    ) -> str:
        models = OPENROUTER_TEST_MODELS if TEST_MODE else OPENROUTER_WORK_MODELS
        for model in models:
            try:
                # Use 15s timeout as requested by user
                return or_generate_content(
                    contents=contents,
                    system_instruction=system_instruction,
                    model=model,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    timeout=15,
                )
            except Exception as e:
                print(f"Model {model} failed or timed out: {e}, trying next...", flush=True)
        raise Exception("All OpenRouter models failed")

    generate_content = _wrap_generate_content

elif PROVIDER == "google":
    from tools.gemini import (
        generate_content as gemini_generate_content,
    )
    from tools.gemini import (
        get_working_key as gemini_get_working_key,
    )

    def get_working_key() -> bool:
        model = GEMINI_TEST_MODELS[0] if TEST_MODE else GEMINI_WORK_MODELS[0]
        return gemini_get_working_key(model)

    def _wrap_generate_content(
        contents: str,
        system_instruction: str,
        max_output_tokens: int = 32768,
        temperature: float = 0.1,
    ) -> str:
        models = GEMINI_TEST_MODELS if TEST_MODE else GEMINI_WORK_MODELS
        for model in models:
            try:
                return gemini_generate_content(
                    contents=contents,
                    system_instruction=system_instruction,
                    model=model,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                )
            except Exception as e:
                print(f"Model {model} failed: {e}, trying next...", flush=True)
        raise Exception("All Gemini models failed")

    generate_content = _wrap_generate_content

else:
    print(f"[ERROR] Unknown provider: {PROVIDER}")
    print("Set PROVIDER=google or PROVIDER=openrouter in .env")
    exit(1)
