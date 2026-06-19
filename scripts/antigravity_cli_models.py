"""Print the model list exposed by the installed Antigravity CLI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from tools.antigravity_cli_models import (
    PROBE_PROMPT,
    AntigravityCliModelError,
    AntigravityCliRegistry,
    JsonObject,
    ModelDefinition,
    ProbeResult,
    load_registry,
    probe_models,
)
from tools.printer import printer as pr


@dataclass(frozen=True)
class CliArgs:
    json_output: bool
    probe: bool
    model: str | None
    limit: int | None
    timeout: int
    log_file: Path | None


def parse_args(argv: Sequence[str] | None = None) -> CliArgs:
    parser = argparse.ArgumentParser(
        description="List models exposed by the installed Antigravity CLI."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Make explicit Antigravity CLI print requests to check callability.",
    )
    parser.add_argument(
        "--model",
        help="Probe one available model name instead of the full model list.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit probe requests to the first N available models.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="CLI command timeout in seconds.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Pass an explicit Antigravity CLI log file path.",
    )
    namespace = parser.parse_args(argv)

    if namespace.model and not namespace.probe:
        parser.error("--model requires --probe")
    if namespace.limit is not None and not namespace.probe:
        parser.error("--limit requires --probe")
    if namespace.timeout < 1:
        parser.error("--timeout must be greater than zero")

    return CliArgs(
        json_output=namespace.json_output,
        probe=namespace.probe,
        model=namespace.model,
        limit=namespace.limit,
        timeout=namespace.timeout,
        log_file=namespace.log_file,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        registry = load_registry(timeout=args.timeout, log_file=args.log_file)
        probe_results = (
            probe_models(
                registry,
                selected_model=args.model,
                limit=args.limit,
                timeout=args.timeout,
                log_file=args.log_file,
            )
            if args.probe
            else []
        )
    except AntigravityCliModelError as error:
        if args.json_output:
            _write_json({"error": str(error)})
        else:
            pr.red(f"ERROR: {error}")
        return 1

    if args.json_output:
        _write_registry_json(registry, probe_results=probe_results)
    else:
        _render_human(registry, probe_results=probe_results)
    return 0


def _render_human(
    registry: AntigravityCliRegistry,
    *,
    probe_results: list[ProbeResult],
) -> None:
    source = registry.source
    pr.green("Antigravity CLI model registry")
    pr.summary("CLI path", str(source.cli_path))
    pr.summary("CLI version", source.cli_version)
    pr.summary("List command", " ".join(source.list_command))

    pr.green("Available models")
    models = registry.display_models()
    if models:
        for model in models:
            pr.white(_format_model(model))
    else:
        pr.amber("No models matched the selected display mode.")

    if probe_results:
        pr.green("Probe results")
        for result in probe_results:
            pr.white(_format_probe_result(result))
    else:
        pr.amber(
            "Prompt callability not checked. Use --probe to make explicit "
            "Antigravity CLI print requests."
        )


def _write_registry_json(
    registry: AntigravityCliRegistry,
    *,
    probe_results: list[ProbeResult],
) -> None:
    payload = registry.to_json()
    if probe_results:
        payload["probe"] = {
            "prompt": PROBE_PROMPT,
            "results": [result.to_json() for result in probe_results],
        }
    _write_json(payload)


def _write_json(payload: JsonObject) -> None:
    # JSON mode bypasses the project printer so stdout remains machine-readable.
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _format_model(model: ModelDefinition) -> str:
    default = " default" if model.is_default else ""
    return (
        f"{model.name:<36} provider={model.provider or '-':<10} "
        f"tier={model.tier or '-':<12} id={model.model_id or '-'}{default}"
    )


def _format_probe_result(result: ProbeResult) -> str:
    detail = result.response_text if result.status == "ok" else result.error
    return f"{result.model_name:<36} {result.status:<7} {detail or '-'}"


if __name__ == "__main__":
    raise SystemExit(main())
