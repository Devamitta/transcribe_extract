# DeepSeek API client for direct LLM access without OpenRouter.

import os

import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from tools.openai_compat import RateLimiter, extract_content, post_chat_completion

load_dotenv()

BASE_URL = "https://api.deepseek.com"


class RetriableDeepSeekError(Exception):
    """Signals a transient DeepSeek API failure that should be retried."""


class DeepSeekClient(RateLimiter):
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = BASE_URL


_client: DeepSeekClient | None = None


def _get_api_key() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("No DEEPSEEK_API_KEY found in .env")
    return api_key


def _get_client() -> DeepSeekClient:
    global _client

    api_key = _get_api_key()
    if _client is None or _client.api_key != api_key:
        _client = DeepSeekClient(api_key)
    return _client


def get_working_key() -> bool:
    """Test if the API key works using the DeepSeek API."""
    try:
        client = _get_client()
        print("Testing DeepSeek API key...", flush=True)
        client.wait_for_rate_limit()
        resp = requests.post(
            f"{client.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {client.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print("[OK] DEEPSEEK_API_KEY works", flush=True)
            return True
        print(f"[ERROR] DeepSeek API key failed: {resp.status_code}", flush=True)
        return False
    except Exception as e:
        print(f"[ERROR] DeepSeek API key failed: {e}", flush=True)
        return False


@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(
        (requests.exceptions.RequestException, RetriableDeepSeekError)
    ),
)
def generate_content(
    contents: str,
    system_instruction: str,
    model: str,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
    timeout: int = 30,
) -> str:
    """Generate content using DeepSeek API."""
    client = _get_client()
    client.wait_for_rate_limit()
    resp = post_chat_completion(
        base_url=client.base_url,
        api_key=client.api_key,
        model=model,
        system_instruction=system_instruction,
        contents=contents,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        timeout=timeout,
        log_request_errors=True,
    )

    if resp.status_code == 429 or 500 <= resp.status_code < 600:
        raise RetriableDeepSeekError(
            f"DeepSeek API transient error: {resp.status_code} {resp.text}"
        )

    if resp.status_code != 200:
        raise ValueError(f"DeepSeek API error: {resp.status_code} {resp.text}")

    return extract_content(resp.json(), "DeepSeek")


SUPPORTED_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro"]


def list_models() -> list[str]:
    """List available DeepSeek models.

    Returns a hardcoded list of supported models since DeepSeek docs
    indicate a fixed set of available models.
    """
    return sorted(SUPPORTED_MODELS)


if __name__ == "__main__":
    models = list_models()
    print(f"=== DEEPSEEK MODELS ({len(models)}) ===")
    for m in models:
        print(f"  {m}")
