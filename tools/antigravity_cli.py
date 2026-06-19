"""Antigravity CLI provider for headless LLM requests through the local agy executable."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

from tools.antigravity_cli_models import (
    AntigravityCliModelError,
    clean_terminal_output,
    locate_executable,
    run_antigravity_print,
)

PROBE_CONTENTS = "Return OK only."
PROBE_SYSTEM_INSTRUCTION = "Return exactly OK and nothing else."


class AntigravityCliProviderError(RuntimeError):
    """Raised when the Antigravity CLI provider cannot complete a request."""


def get_working_key(model: str = "Gemini 3.5 Flash (Low)") -> bool:
    """Check whether Antigravity CLI can call the selected model."""

    try:
        response = generate_content(
            contents=PROBE_CONTENTS,
            system_instruction=PROBE_SYSTEM_INSTRUCTION,
            model=model,
            max_output_tokens=10,
            temperature=0.0,
            timeout=60,
        )
    except Exception as e:
        print(f"[ERROR] Antigravity CLI model {model} failed: {e}", flush=True)
        return False

    return bool(response.strip())


def generate_content(
    contents: str,
    system_instruction: str,
    model: str,
    max_output_tokens: int = 32768,
    temperature: float = 0.1,
    timeout: int = 120,
) -> str:
    """Generate content using Antigravity CLI print mode."""

    agy_path = _locate_antigravity()
    prompt = _build_prompt(contents, system_instruction, max_output_tokens, temperature)

    print(f"  -> antigravity-cli {model} (timeout={timeout}s)...", flush=True)
    try:
        result = run_antigravity_print(
            agy_path,
            model,
            prompt,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise AntigravityCliProviderError(
            f"{model} timed out after {timeout}s"
        ) from error
    except AntigravityCliModelError as error:
        raise AntigravityCliProviderError(str(error)) from error

    if result.returncode != 0:
        raise AntigravityCliProviderError(
            f"{model} failed: {_brief_command_error(result.stdout, result.stderr, result.returncode)}"
        )

    response = _extract_response(result.stdout)
    if response is None or not response.strip():
        raise AntigravityCliProviderError(f"{model} returned an empty response")
    return response


def _locate_antigravity() -> Path:
    try:
        return locate_executable("agy")
    except AntigravityCliModelError as error:
        raise AntigravityCliProviderError("agy executable not found on PATH") from error


def _build_prompt(
    contents: str, system_instruction: str, max_output_tokens: int, temperature: float
) -> str:
    return (
        "Follow the system instruction below. Treat the USER CONTENT section as the "
        "full user input. Do not inspect local files or use tools unless the user "
        "content explicitly requires it.\n\n"
        "SYSTEM INSTRUCTION:\n"
        f"{system_instruction}\n\n"
        "REQUEST SETTINGS:\n"
        f"- max_output_tokens: {max_output_tokens}\n"
        f"- temperature: {temperature}\n"
        "\nUSER CONTENT:\n"
        f"{contents}\n"
    )


def _extract_response(stdout: str) -> str | None:
    cleaned = clean_terminal_output(stdout)
    if not cleaned:
        return None

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned

    if isinstance(parsed, str):
        return parsed
    if not isinstance(parsed, dict):
        return cleaned

    response = cast(dict[str, Any], parsed).get("response")
    if isinstance(response, str):
        return response
    text = cast(dict[str, Any], parsed).get("text")
    if isinstance(text, str):
        return text
    content = cast(dict[str, Any], parsed).get("content")
    if isinstance(content, str):
        return content
    return cleaned


def _brief_command_error(
    stdout: str | None, stderr: str | None, returncode: int
) -> str:
    message = clean_terminal_output(stderr) or clean_terminal_output(stdout)
    if not message:
        message = str(returncode)
    if len(message) <= 500:
        return message
    return f"{message[:497]}..."
