"""Lists and tests the API key(s) for the configured provider."""

import os

from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("PROVIDER", "google").lower()


def _check_gemini() -> None:
    from google import genai

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
            model_names = [m.name for m in models if m.name is not None]
            return True, model_names, ""
        except Exception as e:
            error_str = str(e)
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                return False, [], f"Rate limited: {error_str[:200]}"
            return False, [], f"Error: {error_str[:200]}"

    def test_model(key_name: str, api_key: str, model: str) -> tuple[bool, str]:
        from google.genai import types

        client = genai.Client(api_key=api_key)
        try:
            response = client.models.generate_content(
                model=model,
                contents="hi",
                config=types.GenerateContentConfig(
                    max_output_tokens=5, temperature=0.0
                ),
            )
            if response.text:
                return True, response.text
            return False, "Empty response"
        except Exception as e:
            return False, str(e)[:100]

    keys = get_api_keys()
    if not keys:
        print("No GEMINI_API_KEY found in .env")
        return

    print(f"Found {len(keys)} Gemini API key(s)\n", flush=True)
    working = 0
    failed = 0

    for key_name, api_key in keys:
        print(f"=== {key_name} ===", flush=True)
        ok, models, error = list_models_for_key(key_name, api_key)
        if ok:
            print(f"  Available models: {models}")
            working += 1
            if models:
                test_ok, test_result = test_model(key_name, api_key, models[0])
                if test_ok:
                    print(f"  Test with {models[0]}: OK -> '{test_result}'")
                else:
                    print(f"  Test with {models[0]}: FAILED -> {test_result}")
        else:
            print(f"  FAILED: {error}")
            failed += 1
        print(flush=True)

    print(f"Summary: {working} keys with models listed, {failed} failed")


def _check_deepseek() -> None:
    from tools.deepseek import get_working_key

    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        print("No DEEPSEEK_API_KEY found in .env")
        return
    print(f"DEEPSEEK_API_KEY: {'*' * 8}{key[-4:]}")
    get_working_key()


def _check_openrouter() -> None:
    from tools.openrouter import get_working_key

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("No OPENROUTER_API_KEY found in .env")
        return
    print(f"OPENROUTER_API_KEY: {'*' * 8}{key[-4:]}")
    get_working_key()


def main() -> None:
    print(f"Provider: {PROVIDER}\n", flush=True)
    if PROVIDER == "google":
        _check_gemini()
    elif PROVIDER == "deepseek":
        _check_deepseek()
    elif PROVIDER == "openrouter":
        _check_openrouter()
    else:
        print(f"[ERROR] Unknown provider: {PROVIDER}")
        print("Set PROVIDER=google, PROVIDER=deepseek, or PROVIDER=openrouter in .env")


if __name__ == "__main__":
    main()
