"""Retry helpers for YouTube chapter LLM calls."""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Callable

from tools.printer import printer as pr

LLMRequest = Callable[[int], str | None]


class LLMRetryError(RuntimeError):
    """Raised when an LLM request fails after all retry attempts."""


def retry_llm_request(
    request: LLMRequest,
    *,
    file_name: str,
    action: str,
    max_attempts: int = 3,
    retry_delay_s: float = 3.0,
) -> str:
    """Run an LLM request until it returns text or exhausts retry attempts."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_error = "no attempts run"
    for attempt in range(1, max_attempts + 1):
        try:
            response = request(attempt)
        except concurrent.futures.TimeoutError:
            last_error = "timeout"
            pr.amber(f"    LLM {action} attempt {attempt}/{max_attempts} timed out")
        except Exception as exc:
            last_error = str(exc) or exc.__class__.__name__
            pr.amber(
                f"    LLM {action} attempt {attempt}/{max_attempts} failed: {last_error}"
            )
        else:
            if response:
                return response
            last_error = "empty response"
            pr.amber(f"    Empty response from LLM on attempt {attempt}/{max_attempts}")

        if attempt < max_attempts:
            pr.amber(f"    Retrying {file_name}...")
            time.sleep(retry_delay_s)

    raise LLMRetryError(
        f"{action} failed for {file_name} after {max_attempts} attempts: {last_error}"
    )
