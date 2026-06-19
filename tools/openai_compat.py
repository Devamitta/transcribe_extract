"""Shared OpenAI-compatible chat-completions HTTP helpers used by the DeepSeek and OpenRouter clients."""

import time
from typing import Any

import requests

MIN_REQUEST_INTERVAL = 1


class RateLimiter:
    """Spaces consecutive requests at least MIN_REQUEST_INTERVAL seconds apart."""

    def __init__(self) -> None:
        self.last_request_time: float = 0.0

    def wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            wait = MIN_REQUEST_INTERVAL - elapsed
            print(f"Rate limiting: waiting {wait:.1f}s...", flush=True)
            time.sleep(wait)
        self.last_request_time = time.time()


def post_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    system_instruction: str,
    contents: str,
    max_output_tokens: int,
    temperature: float,
    timeout: int,
    extra_headers: dict[str, str] | None = None,
    log_request_errors: bool = False,
) -> requests.Response:
    """POST a chat-completions request and return the raw response.

    Timeouts are logged and re-raised; other request failures are logged only
    when log_request_errors is set. Status-code classification stays in the
    caller because it differs per provider.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    print(f"  -> {model} (timeout={timeout}s)...", flush=True)
    try:
        return requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": contents},
                ],
                "max_tokens": max_output_tokens,
                "temperature": temperature,
            },
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        print(f"  [TIMEOUT] {model} exceeded {timeout}s", flush=True)
        raise
    except requests.exceptions.RequestException as exc:
        if log_request_errors:
            print(f"  [REQUEST ERROR] {model}: {exc}", flush=True)
        raise


def extract_content(data: dict[str, Any], label: str) -> str:
    """Parse a chat-completions payload, falling back to the reasoning trace."""
    if not data.get("choices"):
        raise ValueError(f"Empty response from {label} API")

    message = data["choices"][0]["message"]
    content = message.get("content") or ""
    if not content:
        finish_reason = data["choices"][0].get("finish_reason", "unknown")
        reasoning = message.get("reasoning_content") or ""
        print(
            f"  [{label}] null/empty content (finish_reason={finish_reason},"
            f" reasoning_len={len(reasoning)})",
            flush=True,
        )
        return reasoning  # fall back to reasoning trace if content is absent
    return content
