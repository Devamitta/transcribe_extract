#!/usr/bin/env python3
"""Lists available Gemini API keys and tests them to verify they work."""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()


def get_api_keys() -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for i in range(1, 100):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append((f"GEMINI_API_KEY_{i}", key))

    if not keys:
        key = os.getenv("GEMINI_API_KEY")
        if key:
            keys.append(("GEMINI_API_KEY", key))

    return keys


def list_models_for_key(key_name: str, api_key: str) -> tuple[bool, list[str], str]:
    client = genai.Client(api_key=api_key)

    try:
        models = client.models.list()
        model_names = [m.name for m in models]
        return True, model_names, ""
    except Exception as e:
        error_str = str(e)
        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
            return False, [], f"Rate limited: {error_str[:200]}"
        return False, [], f"Error: {error_str[:200]}"


def test_model(key_name: str, api_key: str, model: str) -> tuple[bool, str]:
    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model,
            contents="hi",
            max_output_tokens=5,
        )
        if response.text:
            return True, response.text
        return False, "Empty response"
    except Exception as e:
        return False, str(e)[:100]


def main() -> None:
    keys = get_api_keys()
    if not keys:
        print("No GEMINI_API_KEY found in .env")
        return

    print(f"Found {len(keys)} API keys\n", flush=True)

    working: int = 0
    failed: int = 0

    for key_name, api_key in keys:
        print(f"=== {key_name} ===", flush=True)

        ok, models, error = list_models_for_key(key_name, api_key)

        if ok:
            print(f"  Available models: {models}")
            working += 1

            # Try a quick test with the first available model
            if models:
                test_model_name = models[0]
                test_ok, test_result = test_model(key_name, api_key, test_model_name)
                if test_ok:
                    print(f"  Test with {test_model_name}: OK -> '{test_result}'")
                else:
                    print(f"  Test with {test_model_name}: FAILED -> {test_result}")
        else:
            print(f"  FAILED: {error}")
            failed += 1

        print(flush=True)

    print(f"Summary: {working} keys with models listed, {failed} failed")


if __name__ == "__main__":
    main()
