"""Print the model registry exposed by the installed Gemini CLI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Sequence

from tools.gemini_cli_models import (
    PROBE_PROMPT,
    AliasDefinition,
    GeminiCliModelError,
    GeminiCliRegistry,
    JsonObject,
    JsonValue,
    ModelDefinition,
    ProbeResult,
    load_registry,
    probe_models,
)
from tools.printer import printer as pr


@dataclass(frozen=True)
class CliArgs:
    json_output: bool
    include_all: bool
    probe: bool
    model: str | None
    limit: int | None
    timeout: int


def parse_args(argv: Sequence[str] | None = None) -> CliArgs:
    parser = argparse.ArgumentParser(
        description="List model definitions exposed by the installed Gemini CLI."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="include_all",
        help="Include hidden/helper definitions in addition to visible models.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Make explicit Gemini CLI requests to check account callability.",
    )
    parser.add_argument(
        "--model",
        help="Probe one concrete model ID instead of the visible model list.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit probe requests to the first N visible concrete models.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Probe timeout in seconds.",
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
        include_all=namespace.include_all,
        probe=namespace.probe,
        model=namespace.model,
        limit=namespace.limit,
        timeout=namespace.timeout,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        registry = load_registry()
        probe_results = (
            probe_models(
                registry,
                selected_model=args.model,
                limit=args.limit,
                timeout=args.timeout,
            )
            if args.probe
            else []
        )
    except GeminiCliModelError as error:
        if args.json_output:
            _write_json({"error": str(error)})
        else:
            pr.red(f"ERROR: {error}")
        return 1

    if args.json_output:
        _write_registry_json(
            registry,
            include_all=args.include_all,
            probe_results=probe_results,
        )
    else:
        _render_human(
            registry,
            include_all=args.include_all,
            probe_results=probe_results,
        )
    return 0


def _render_human(
    registry: GeminiCliRegistry,
    *,
    include_all: bool,
    probe_results: list[ProbeResult],
) -> None:
    source = registry.source
    pr.green("Gemini CLI model registry")
    pr.summary("CLI path", str(source.cli_path))
    pr.summary("Bundle entry", str(source.bundle_entry))
    pr.summary("Bundle dir", str(source.bundle_dir))
    pr.summary("CLI version", source.cli_version)
    pr.summary("Package version", source.package_version)
    pr.summary("Registry module", str(source.source_module))

    model_heading = (
        "All model definitions" if include_all else "Visible concrete models"
    )
    pr.green(model_heading)
    models = registry.display_models(include_all=include_all)
    if models:
        for model in models:
            pr.white(_format_model(model, include_all=include_all))
    else:
        pr.amber("No models matched the selected display mode.")

    alias_heading = "All aliases" if include_all else "Visible and standard aliases"
    pr.green(alias_heading)
    aliases = registry.display_aliases(include_all=include_all)
    if aliases:
        for alias in aliases:
            pr.white(_format_alias(alias))
    else:
        pr.amber("No aliases matched the selected display mode.")

    if probe_results:
        pr.green("Probe results")
        for result in probe_results:
            pr.white(_format_probe_result(result))
    else:
        pr.amber(
            "Account/auth availability not checked. Use --probe to make explicit "
            "Gemini CLI requests."
        )


def _write_registry_json(
    registry: GeminiCliRegistry,
    *,
    include_all: bool,
    probe_results: list[ProbeResult],
) -> None:
    payload = registry.to_json(include_all=include_all)
    if probe_results:
        payload["account_availability"] = _probe_availability(probe_results)
        payload["probe"] = {
            "prompt": PROBE_PROMPT,
            "results": [result.to_json() for result in probe_results],
        }
    _write_json(payload)


def _write_json(payload: JsonObject) -> None:
    # JSON mode bypasses the project printer so stdout remains machine-readable.
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _format_model(model: ModelDefinition, *, include_all: bool) -> str:
    preview = "preview" if model.is_preview else "stable"
    visibility = "visible" if model.is_visible else "hidden"
    concrete = "concrete" if model.is_concrete else "alias"
    suffix = f"  {visibility} {concrete}" if include_all else ""
    return (
        f"{model.model_id:<38} tier={model.tier or '-':<10} "
        f"family={model.family or '-':<10} {preview:<7} "
        f"features={_format_features(model.features)}{suffix}"
    )


def _format_alias(alias: AliasDefinition) -> str:
    visibility = "visible" if alias.is_visible else "hidden"
    standard = "standard" if alias.is_standard else "helper"
    return (
        f"{alias.name:<28} tier={alias.tier or '-':<10} "
        f"target={alias.target_model or '-':<28} "
        f"extends={alias.extends or '-':<16} {visibility:<7} {standard:<8} "
        f"{_format_resolution(alias.resolution)}"
    )


def _format_probe_result(result: ProbeResult) -> str:
    detail = result.response_text if result.status == "ok" else result.error
    return f"{result.model_id:<38} {result.status:<7} {detail or '-'}"


def _format_features(features: dict[str, bool]) -> str:
    if not features:
        return "-"
    return ",".join(
        f"{name}={'yes' if value else 'no'}" for name, value in sorted(features.items())
    )


def _format_resolution(resolution: JsonObject | None) -> str:
    if resolution is None:
        return "resolution=-"

    default = resolution.get("default")
    pieces = [f"default={default}" if isinstance(default, str) else "default=-"]
    contexts = resolution.get("contexts")
    if isinstance(contexts, list) and contexts:
        formatted_contexts = [
            _format_resolution_context(context)
            for context in contexts
            if isinstance(context, dict)
        ]
        if formatted_contexts:
            pieces.append("contexts=" + " | ".join(formatted_contexts))
    return "resolution=" + "; ".join(pieces)


def _format_resolution_context(context: JsonValue) -> str:
    if not isinstance(context, dict):
        return "-"
    condition = context.get("condition")
    target = context.get("target")
    condition_text = json.dumps(condition, sort_keys=True, separators=(",", ":"))
    target_text = target if isinstance(target, str) else "-"
    return f"{condition_text}->{target_text}"


def _probe_availability(results: list[ProbeResult]) -> JsonObject:
    ok_count = sum(1 for result in results if result.status == "ok")
    failed_count = sum(1 for result in results if result.status == "failed")
    if failed_count == 0:
        status = "checked_ok"
    elif ok_count > 0:
        status = "checked_partial"
    else:
        status = "checked_failed"
    return {
        "status": status,
        "checked": len(results),
        "ok": ok_count,
        "failed": failed_count,
    }


if __name__ == "__main__":
    raise SystemExit(main())
