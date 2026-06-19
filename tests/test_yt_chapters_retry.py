"""Tests for YouTube chapter LLM retry helpers."""

from __future__ import annotations

import concurrent.futures

import pytest

from tools import yt_chapters_retry
from tools.yt_chapters_retry import LLMRetryError, retry_llm_request


def noop_sleep(_seconds: float) -> None:
    pass


def noop_amber(_message: str) -> None:
    pass


def test_retry_returns_success_after_empty_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    responses: list[str | None] = ["", None, "[0.0] Opening"]

    monkeypatch.setattr(yt_chapters_retry.time, "sleep", noop_sleep)
    monkeypatch.setattr(yt_chapters_retry.pr, "amber", noop_amber)

    def request(attempt: int) -> str | None:
        calls.append(attempt)
        return responses[attempt - 1]

    result = retry_llm_request(
        request,
        file_name="talk.md",
        action="chapter generation",
    )

    assert result == "[0.0] Opening"
    assert calls == [1, 2, 3]


def test_retry_returns_success_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    monkeypatch.setattr(yt_chapters_retry.time, "sleep", noop_sleep)
    monkeypatch.setattr(yt_chapters_retry.pr, "amber", noop_amber)

    def request(attempt: int) -> str | None:
        calls.append(attempt)
        if attempt == 1:
            raise concurrent.futures.TimeoutError
        return "[0.0] Opening"

    result = retry_llm_request(
        request,
        file_name="talk.md",
        action="chapter generation",
    )

    assert result == "[0.0] Opening"
    assert calls == [1, 2]


def test_retry_returns_success_after_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    monkeypatch.setattr(yt_chapters_retry.time, "sleep", noop_sleep)
    monkeypatch.setattr(yt_chapters_retry.pr, "amber", noop_amber)

    def request(attempt: int) -> str | None:
        calls.append(attempt)
        if attempt == 1:
            raise RuntimeError("provider failed")
        return "[0.0] Opening"

    result = retry_llm_request(
        request,
        file_name="talk.md",
        action="chapter generation",
    )

    assert result == "[0.0] Opening"
    assert calls == [1, 2]


def test_retry_returns_success_after_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    responses = ["not chapter output", "[0.0] Opening"]

    monkeypatch.setattr(yt_chapters_retry.time, "sleep", noop_sleep)
    monkeypatch.setattr(yt_chapters_retry.pr, "amber", noop_amber)

    def request(attempt: int) -> str | None:
        calls.append(attempt)
        return responses[attempt - 1]

    def validate(response: str) -> str | None:
        return None if response.startswith("[0.0]") else "malformed output"

    result = retry_llm_request(
        request,
        file_name="talk.md",
        action="chapter generation",
        validate_response=validate,
    )

    assert result == "[0.0] Opening"
    assert calls == [1, 2]


def test_retry_raises_after_all_attempts_are_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    monkeypatch.setattr(yt_chapters_retry.time, "sleep", noop_sleep)
    monkeypatch.setattr(yt_chapters_retry.pr, "amber", noop_amber)

    def request(attempt: int) -> str | None:
        calls.append(attempt)
        return ""

    with pytest.raises(LLMRetryError, match="after 3 attempts: empty response"):
        retry_llm_request(
            request,
            file_name="talk.md",
            action="chapter generation",
        )

    assert calls == [1, 2, 3]


def test_retry_raises_after_validation_failures_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    monkeypatch.setattr(yt_chapters_retry.time, "sleep", noop_sleep)
    monkeypatch.setattr(yt_chapters_retry.pr, "amber", noop_amber)

    def request(attempt: int) -> str | None:
        calls.append(attempt)
        return "not chapter output"

    def validate(_response: str) -> str | None:
        return "malformed output"

    with pytest.raises(LLMRetryError, match="after 3 attempts: malformed output"):
        retry_llm_request(
            request,
            file_name="talk.md",
            action="chapter generation",
            validate_response=validate,
        )

    assert calls == [1, 2, 3]
