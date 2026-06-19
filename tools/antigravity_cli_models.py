"""Discover and normalize the model list exposed by the installed Antigravity CLI."""

from __future__ import annotations

import errno
import json
import os
import pty
import re
import select
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]

PROBE_PROMPT = "Return OK only."
DEFAULT_EXECUTABLE = "agy"

_ANSI_RE = re.compile(
    r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))"
)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_JSON_MODEL_KEYS = (
    "displayName",
    "display_name",
    "name",
    "title",
    "label",
    "model",
    "modelId",
    "model_id",
    "id",
)
_JSON_MODEL_LIST_KEYS = (
    "models",
    "availableModels",
    "available_models",
    "items",
    "data",
)
_ERROR_MARKERS = {
    "sign_in": (
        "please sign in",
        "not signed in",
        "not logged in",
        "msg_not_logged_in",
    ),
    "no_models": ("no available models", "no models found"),
    "timeout": ("timed out waiting for available models",),
}


class AntigravityCliModelError(RuntimeError):
    """Raised when Antigravity CLI model discovery cannot complete."""


@dataclass(frozen=True)
class CommandResult:
    """Captured result from an Antigravity CLI command."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str | None


@dataclass(frozen=True)
class SourceMetadata:
    """Metadata describing where the Antigravity model list came from."""

    cli_path: Path
    cli_version: str
    list_command: list[str]

    def to_json(self) -> JsonObject:
        return {
            "cli_path": str(self.cli_path),
            "cli_version": self.cli_version,
            "list_command": cast(list[JsonValue], self.list_command.copy()),
        }


@dataclass(frozen=True)
class ModelDefinition:
    """A normalized Antigravity CLI model entry."""

    name: str
    model_id: str | None
    provider: str | None
    tier: str | None
    is_default: bool
    raw_line: str

    def to_json(self) -> JsonObject:
        return {
            "name": self.name,
            "model_id": self.model_id,
            "provider": self.provider,
            "tier": self.tier,
            "is_default": self.is_default,
            "raw_line": self.raw_line,
        }


@dataclass(frozen=True)
class ProbeResult:
    """Result from an explicit Antigravity CLI prompt request."""

    model_name: str
    status: Literal["ok", "failed", "skipped"]
    command: list[str]
    returncode: int | None
    response_text: str | None
    stdout: str | None
    stderr: str | None
    error: str | None

    def to_json(self) -> JsonObject:
        return {
            "model_name": self.model_name,
            "status": self.status,
            "command": cast(list[JsonValue], self.command.copy()),
            "returncode": self.returncode,
            "response_text": self.response_text,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
        }


@dataclass(frozen=True)
class AntigravityCliRegistry:
    """Normalized Antigravity CLI model registry plus source metadata."""

    source: SourceMetadata
    models: list[ModelDefinition]

    def display_models(self) -> list[ModelDefinition]:
        return self.models

    def to_json(self) -> JsonObject:
        return {
            "source": self.source.to_json(),
            "account_availability": {
                "status": "checked_by_models_command",
                "note": "`agy models` returned the available model list.",
            },
            "models": [model.to_json() for model in self.display_models()],
        }


def load_registry(
    executable: str = DEFAULT_EXECUTABLE,
    *,
    timeout: int = 120,
    log_file: Path | None = None,
    use_pty: bool = True,
) -> AntigravityCliRegistry:
    """Load the available Antigravity CLI models by running `agy models`."""

    cli_path = locate_executable(executable)
    cli_version = run_antigravity_version(cli_path)
    result = run_antigravity_models(
        cli_path,
        timeout=timeout,
        log_file=log_file,
        use_pty=use_pty,
    )

    if result.returncode != 0:
        _raise_known_output_error(result.stdout, result.stderr)
        raise AntigravityCliModelError(
            f"agy models failed: {_brief_error(result.stdout, result.stderr, result.returncode)}"
        )

    _raise_known_output_error(result.stdout, result.stderr)
    source = SourceMetadata(
        cli_path=cli_path,
        cli_version=cli_version,
        list_command=result.command,
    )
    return normalize_registry(result.stdout, source)


def locate_executable(name: str) -> Path:
    executable = shutil.which(name)
    if executable is None:
        raise AntigravityCliModelError(f"Required executable not found on PATH: {name}")
    return Path(executable)


def run_antigravity_version(cli_path: Path) -> str:
    result = subprocess.run(
        [str(cli_path), "--version"],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise AntigravityCliModelError(
            f"agy --version failed: {_brief_error(result.stdout, result.stderr, result.returncode)}"
        )
    version = result.stdout.strip()
    if not version:
        raise AntigravityCliModelError("agy --version returned empty output")
    return version


def run_antigravity_models(
    cli_path: Path,
    *,
    timeout: int = 120,
    log_file: Path | None = None,
    use_pty: bool = True,
) -> CommandResult:
    command = _with_log_file([str(cli_path), "models"], log_file)
    try:
        return _run_cli_command(command, timeout=timeout, use_pty=use_pty)
    except subprocess.TimeoutExpired as error:
        output = _decode_timeout_output(error.output)
        raise AntigravityCliModelError(
            f"agy models timed out after {timeout}s: {output or 'no output'}"
        ) from error


def normalize_registry(
    raw_output: str, source: SourceMetadata
) -> AntigravityCliRegistry:
    """Normalize raw `agy models` output into structured model entries."""

    _raise_known_output_error(raw_output, None)
    models = _models_from_json_output(raw_output)
    if models is None:
        models = _models_from_text_output(raw_output)

    models = _dedupe_models(models)
    if not models:
        cleaned = clean_terminal_output(raw_output)
        preview = cleaned[:500] if cleaned else "empty output"
        raise AntigravityCliModelError(
            f"No Antigravity models found in agy models output: {preview}"
        )

    return AntigravityCliRegistry(source=source, models=models)


def probe_models(
    registry: AntigravityCliRegistry,
    *,
    selected_model: str | None = None,
    limit: int | None = None,
    timeout: int = 120,
    log_file: Path | None = None,
    use_pty: bool = True,
) -> list[ProbeResult]:
    """Make explicit Antigravity CLI prompt requests for available models."""

    if selected_model:
        selected = next(
            (
                model
                for model in registry.models
                if model.name == selected_model or model.model_id == selected_model
            ),
            None,
        )
        if selected is None:
            raise AntigravityCliModelError(
                f"Probe model is not in the Antigravity CLI model list: {selected_model}"
            )
        models = [selected]
    else:
        models = registry.display_models()

    if limit is not None:
        if limit < 1:
            raise AntigravityCliModelError("--limit must be greater than zero")
        models = models[:limit]

    if not models:
        raise AntigravityCliModelError("No Antigravity models available to probe")

    return [
        probe_model(
            registry.source.cli_path,
            model.name,
            timeout=timeout,
            log_file=log_file,
            use_pty=use_pty,
        )
        for model in models
    ]


def probe_model(
    cli_path: Path,
    model_name: str,
    *,
    timeout: int = 120,
    log_file: Path | None = None,
    use_pty: bool = True,
) -> ProbeResult:
    """Make one minimal Antigravity CLI prompt request for a model."""

    command = build_antigravity_print_command(
        cli_path,
        model_name,
        PROBE_PROMPT,
        timeout=timeout,
        log_file=log_file,
    )
    try:
        result = run_antigravity_print(
            cli_path,
            model_name,
            PROBE_PROMPT,
            timeout=timeout,
            log_file=log_file,
            use_pty=use_pty,
        )
    except subprocess.TimeoutExpired as error:
        return ProbeResult(
            model_name=model_name,
            status="failed",
            command=command,
            returncode=None,
            response_text=None,
            stdout=_strip_or_none(_decode_timeout_output(error.output)),
            stderr=_strip_or_none(_decode_timeout_output(error.stderr)),
            error=f"Timed out after {timeout}s",
        )

    stdout = _strip_or_none(clean_terminal_output(result.stdout))
    stderr = _strip_or_none(clean_terminal_output(result.stderr or ""))
    response_text = _extract_response_text(stdout)
    if result.returncode == 0 and response_text:
        return ProbeResult(
            model_name=model_name,
            status="ok",
            command=command,
            returncode=result.returncode,
            response_text=response_text,
            stdout=stdout,
            stderr=stderr,
            error=None,
        )

    return ProbeResult(
        model_name=model_name,
        status="failed",
        command=command,
        returncode=result.returncode,
        response_text=response_text,
        stdout=stdout,
        stderr=stderr,
        error=_brief_error(stdout, stderr, result.returncode),
    )


def build_antigravity_print_command(
    cli_path: Path,
    model_name: str,
    prompt: str,
    *,
    timeout: int,
    log_file: Path | None = None,
) -> list[str]:
    """Build a non-interactive Antigravity CLI print command."""

    return _with_log_file(
        [
            str(cli_path),
            "--model",
            model_name,
            "--print-timeout",
            _duration_seconds(timeout),
            "--print",
            prompt,
        ],
        log_file,
    )


def run_antigravity_print(
    cli_path: Path,
    model_name: str,
    prompt: str,
    *,
    timeout: int = 120,
    log_file: Path | None = None,
    use_pty: bool = True,
) -> CommandResult:
    """Run a non-interactive Antigravity CLI print request."""

    command = build_antigravity_print_command(
        cli_path,
        model_name,
        prompt,
        timeout=timeout,
        log_file=log_file,
    )
    return _run_cli_command(command, timeout=timeout + 5, use_pty=use_pty)


def clean_terminal_output(value: str | None) -> str:
    if value is None:
        return ""
    text = _ANSI_RE.sub("", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_RE.sub("", text).strip()


def _run_cli_command(
    command: list[str], *, timeout: int, use_pty: bool = True
) -> CommandResult:
    if use_pty:
        return _run_pty_command(command, timeout=timeout)
    return _run_pipe_command(command, timeout=timeout)


def _run_pipe_command(command: list[str], *, timeout: int) -> CommandResult:
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=timeout,
    )
    return CommandResult(
        command=command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _run_pty_command(command: list[str], *, timeout: int) -> CommandResult:
    master_fd, slave_fd = pty.openpty()
    process: subprocess.Popen[bytes] | None = None
    chunks: list[bytes] = []

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        slave_fd = -1

        deadline = time.monotonic() + timeout
        while process.poll() is None:
            chunks.extend(_read_available(master_fd, timeout=0))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                output = b"".join(chunks)
                raise subprocess.TimeoutExpired(
                    command,
                    timeout,
                    output=output.decode("utf-8", errors="replace"),
                )
            chunks.extend(_read_available(master_fd, timeout=min(0.1, remaining)))

        chunks.extend(_read_available(master_fd, timeout=0))
        stdout = b"".join(chunks).decode("utf-8", errors="replace")
        return CommandResult(
            command=command,
            returncode=process.returncode,
            stdout=stdout,
            stderr=None,
        )
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        if slave_fd >= 0:
            os.close(slave_fd)
        os.close(master_fd)


def _read_available(fd: int, *, timeout: float) -> list[bytes]:
    readable, _, _ = select.select([fd], [], [], timeout)
    if not readable:
        return []

    chunks: list[bytes] = []
    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError as error:
            if error.errno == errno.EIO:
                break
            raise
        if not chunk:
            break
        chunks.append(chunk)

        readable, _, _ = select.select([fd], [], [], 0)
        if not readable:
            break
    return chunks


def _with_log_file(command: list[str], log_file: Path | None) -> list[str]:
    if log_file is None:
        return command
    return [command[0], "--log-file", str(log_file), *command[1:]]


def _models_from_json_output(raw_output: str) -> list[ModelDefinition] | None:
    parsed = _parse_json_from_output(raw_output)
    if parsed is None:
        return None
    return _models_from_json_value(parsed)


def _parse_json_from_output(raw_output: str) -> JsonValue | None:
    cleaned = clean_terminal_output(raw_output)
    if not cleaned:
        return None

    candidates = [cleaned]
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = cleaned.find(open_char)
        end = cleaned.rfind(close_char)
        if start >= 0 and end > start:
            candidates.append(cleaned[start : end + 1])

    for candidate in candidates:
        try:
            return cast(JsonValue, json.loads(candidate))
        except json.JSONDecodeError:
            continue
    return None


def _models_from_json_value(value: JsonValue) -> list[ModelDefinition]:
    if isinstance(value, list):
        return [
            model
            for item in value
            if (model := _model_from_json_item(item)) is not None
        ]

    if not isinstance(value, dict):
        return []

    for key in _JSON_MODEL_LIST_KEYS:
        items = value.get(key)
        if isinstance(items, list):
            return _models_from_json_value(items)

    if all(isinstance(item, dict) for item in value.values()):
        return [
            model
            for name, item in value.items()
            if (
                model := _model_from_json_item(
                    cast(JsonObject, item),
                    fallback_name=name,
                )
            )
            is not None
        ]

    model = _model_from_json_item(value)
    return [model] if model is not None else []


def _model_from_json_item(
    item: JsonValue, *, fallback_name: str | None = None
) -> ModelDefinition | None:
    if isinstance(item, str):
        return _model_from_name(item, raw_line=item)

    if not isinstance(item, dict):
        return None

    data = cast(JsonObject, item)
    name = _first_string_value(data, _JSON_MODEL_KEYS) or fallback_name
    if name is None:
        return None

    model_id = _first_string_value(data, ("modelId", "model_id", "id", "model"))
    provider = _first_string_value(data, ("provider", "vendor")) or _infer_provider(
        name
    )
    tier = _first_string_value(data, ("tier", "level", "reasoning")) or _infer_tier(
        name
    )
    raw_line = json.dumps(data, sort_keys=True)
    return ModelDefinition(
        name=name,
        model_id=model_id,
        provider=provider,
        tier=_normalize_tier(tier),
        is_default=_any_bool(data, ("isDefault", "default", "selected", "current")),
        raw_line=raw_line,
    )


def _models_from_text_output(raw_output: str) -> list[ModelDefinition]:
    return [
        model
        for line in _clean_lines(raw_output)
        if (model := _model_from_line(line)) is not None
    ]


def _clean_lines(raw_output: str) -> list[str]:
    cleaned = clean_terminal_output(raw_output)
    return [line.strip() for line in cleaned.splitlines() if line.strip()]


def _model_from_line(raw_line: str) -> ModelDefinition | None:
    if _line_is_noise(raw_line):
        return None

    line = _strip_line_prefix(raw_line)
    if not line or _line_is_noise(line):
        return None

    parts = _line_parts(line)
    if not parts:
        return None

    name = _strip_status_markers(parts[0])
    if not name or _line_is_noise(name) or not _looks_like_model_name(name):
        return None

    is_default = _is_default_line(line) or any(_is_default_line(part) for part in parts)
    return _model_from_name(name, raw_line=raw_line, is_default=is_default)


def _line_parts(line: str) -> list[str]:
    if "|" in line:
        parts = [part.strip() for part in line.strip("|").split("|")]
    else:
        parts = [part.strip() for part in re.split(r"\t+|\s{2,}", line)]
    return [part for part in parts if part and not _is_table_separator(part)]


def _strip_line_prefix(line: str) -> str:
    stripped = line.strip()
    stripped = re.sub(r"^(?:[*✓✔●○•>~-]|\d+[.)])\s+", "", stripped)
    stripped = re.sub(r"^\[[ xX✓✔]\]\s+", "", stripped)
    return stripped.strip()


def _strip_status_markers(name: str) -> str:
    value = name.strip()
    value = re.sub(
        r"\s*(?:\((?:default|current|selected)\)|\[(?:default|current|selected)\])\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+(?:default|current|selected)\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip()


def _model_from_name(
    name: str, *, raw_line: str, is_default: bool = False
) -> ModelDefinition:
    model_id = name if _looks_like_identifier(name) else None
    return ModelDefinition(
        name=name,
        model_id=model_id,
        provider=_infer_provider(name),
        tier=_infer_tier(name),
        is_default=is_default,
        raw_line=raw_line,
    )


def _line_is_noise(line: str) -> bool:
    normalized = line.strip().lower()
    if not normalized:
        return True
    if normalized in {"name", "model", "models", "available models"}:
        return True
    if _is_table_separator(normalized):
        return True
    return normalized.startswith(
        (
            "usage:",
            "flags:",
            "available subcommands:",
            "fetching available models",
            "list available models",
            "starting language server",
            "language server will attempt",
            "i0",
            "e0",
        )
    )


def _is_table_separator(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and all(character in "-: " for character in stripped)


def _looks_like_model_name(name: str) -> bool:
    lower = name.lower()
    if any(word in lower for word in ("gemini", "claude", "gpt", "flash", "opus")):
        return True
    return lower in {"pro", "flash", "flash_lite", "flash-lite"}


def _looks_like_identifier(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+-]*", name))


def _infer_provider(name: str) -> str | None:
    lower = name.lower()
    if "gemini" in lower or lower in {"pro", "flash", "flash_lite", "flash-lite"}:
        return "google"
    if "claude" in lower or "opus" in lower:
        return "anthropic"
    if "gpt" in lower:
        return "openai"
    return None


def _infer_tier(name: str) -> str | None:
    match = re.search(r"\(([^)]+)\)\s*$", name)
    if match:
        return _normalize_tier(match.group(1))

    lower = name.lower()
    if "flash-lite" in lower or "flash_lite" in lower:
        return "flash-lite"
    if "flash" in lower:
        return "flash"
    if "pro" in lower:
        return "pro"
    if "thinking" in lower:
        return "thinking"
    return None


def _normalize_tier(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("_", "-")
    return normalized or None


def _first_string_value(data: JsonObject, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _any_bool(data: JsonObject, keys: tuple[str, ...]) -> bool:
    return any(data.get(key) is True for key in keys)


def _is_default_line(line: str) -> bool:
    return bool(
        re.search(
            r"(^|\s|\(|\[)(default|current|selected)(\)|\]|\s|$)",
            line,
            flags=re.IGNORECASE,
        )
    ) or line.lstrip().startswith(("*", "✓", "✔"))


def _dedupe_models(models: list[ModelDefinition]) -> list[ModelDefinition]:
    seen: set[str] = set()
    deduped: list[ModelDefinition] = []
    for model in models:
        key = model.name.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(model)
    return deduped


def _extract_response_text(stdout: str | None) -> str | None:
    if stdout is None:
        return None
    parsed = _parse_json_from_output(stdout)
    if isinstance(parsed, str):
        return parsed.strip()
    if isinstance(parsed, dict):
        for key in ("response", "text", "content", "result"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return stdout.strip() or None


def _raise_known_output_error(stdout: str | None, stderr: str | None) -> None:
    text = clean_terminal_output("\n".join(part for part in (stdout, stderr) if part))
    lower = text.lower()
    if any(marker in lower for marker in _ERROR_MARKERS["sign_in"]):
        raise AntigravityCliModelError(
            "Antigravity CLI reported sign-in is required. Launch `agy` in a normal "
            "terminal and complete auth, then rerun this command."
        )
    if any(marker in lower for marker in _ERROR_MARKERS["timeout"]):
        raise AntigravityCliModelError(
            "Antigravity CLI timed out while fetching available models."
        )
    if any(marker in lower for marker in _ERROR_MARKERS["no_models"]):
        raise AntigravityCliModelError(
            "Antigravity CLI reported that no available models were found."
        )


def _duration_seconds(seconds: int) -> str:
    return f"{seconds}s"


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _brief_error(stdout: str | None, stderr: str | None, returncode: int) -> str:
    message = clean_terminal_output(stderr) or clean_terminal_output(stdout)
    if not message:
        message = f"exit code {returncode}"
    if len(message) <= 500:
        return message
    return f"{message[:497]}..."
