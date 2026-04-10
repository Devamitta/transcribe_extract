# OpenRouter API client for accessing various LLM models with rate limiting and retry logic.

import os
import time
from dotenv import load_dotenv
import requests
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    print("[ERROR] No OPENROUTER_API_KEY found in .env")
    exit(1)

print("Loaded OPENROUTER_API_KEY", flush=True)

MIN_REQUEST_INTERVAL = 30
HOURS_TO_RESET = 24


class OpenRouterClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.failed_models: dict[str, float] = {}
        self.last_request_time = 0.0

    def wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            wait = MIN_REQUEST_INTERVAL - elapsed
            print(f"Rate limiting: waiting {wait:.1f}s...", flush=True)
            time.sleep(wait)
        self.last_request_time = time.time()

    def handle_rate_limit_error(self, model: str) -> bool:
        print(f"{model} rate limited, trying next...", flush=True)
        self.failed_models[model] = time.time()
        return True


client = OpenRouterClient(API_KEY)


def get_working_key() -> bool:
    """Test if the API key works."""
    try:
        print("Testing OpenRouter API key...", flush=True)
        client.wait_for_rate_limit()
        resp = requests.post(
            f"{client.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {client.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            print("[OK] OPENROUTER_API_KEY works", flush=True)
            return True
        print(f"[ERROR] OpenRouter API key failed: {resp.status_code}", flush=True)
        return False
    except Exception as e:
        print(f"[ERROR] OpenRouter API key failed: {e}", flush=True)
        return False


@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception),
)
def generate_content(
    contents: str,
    system_instruction: str,
    model: str,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
) -> str:
    """Generate content using OpenRouter API."""
    client.wait_for_rate_limit()
    print(f"  -> {model}...", flush=True)

    try:
        resp = requests.post(
            f"{client.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {client.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost",
                "X-Title": "Dhamma Extract",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": contents},
                ],
                "max_tokens": max_output_tokens,
                "temperature": temperature,
            },
            timeout=120,
        )
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            client.handle_rate_limit_error(model)
        raise

    if resp.status_code != 200:
        raise ValueError(f"OpenRouter API error: {resp.status_code} {resp.text}")

    data = resp.json()
    if not data.get("choices"):
        raise ValueError("Empty response from OpenRouter API")

    return data["choices"][0]["message"]["content"]


def list_models(free_only: bool = True) -> list[str]:
    """List available OpenRouter models.

    Args:
        free_only: If True, return only free models (ending with :free).
                 If False, return all models.
    """
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"Error fetching models: {resp.status_code}")
            return []

        data = resp.json()
        models = []
        for m in data.get("data", []):
            model_id = m["id"]
            if free_only:
                if model_id.endswith(":free"):
                    models.append(model_id)
            else:
                models.append(model_id)
        return sorted(models)
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []


if __name__ == "__main__":
    import sys

    show_all = "--all" in sys.argv or "-a" in sys.argv
    free_models = list_models(free_only=True)
    all_models = list_models(free_only=False)

    if show_all:
        print(f"=== FREE MODELS ({len(free_models)}) ===")
        for m in free_models:
            print(f"  {m}")
        print(f"\n=== ALL MODELS ({len(all_models)}) ===")
        for m in all_models:
            print(f"  {m}")
    else:
        print(f"=== FREE MODELS ({len(free_models)}) ===")
        for m in free_models:
            print(f"  {m}")
        print(f"\nUse --all to see all {len(all_models)} models")
