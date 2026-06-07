"""Discover and normalize the model registry exposed by the installed Gemini CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]

STANDARD_ALIAS_NAMES = ("auto", "pro", "flash", "flash-lite")
PROBE_PROMPT = "Return OK only."

_REGISTRY_EXPORT_SCRIPT = """
import { pathToFileURL } from 'node:url';

const candidates = process.argv.slice(1);
const errors = [];

for (const candidate of candidates) {
  try {
    const moduleUrl = pathToFileURL(candidate).href;
    const mod = await import(moduleUrl);
    if (Object.prototype.hasOwnProperty.call(mod, 'DEFAULT_MODEL_CONFIGS')) {
      const constantNames = [
        'DEFAULT_GEMINI_MODEL',
        'DEFAULT_GEMINI_MODEL_AUTO',
        'DEFAULT_GEMINI_FLASH_MODEL',
        'DEFAULT_GEMINI_FLASH_LITE_MODEL',
        'PREVIEW_GEMINI_MODEL',
        'PREVIEW_GEMINI_MODEL_AUTO',
        'PREVIEW_GEMINI_FLASH_MODEL',
        'PREVIEW_GEMINI_FLASH_LITE_MODEL',
      ];
      const constants = {};
      for (const name of constantNames) {
        constants[name] = mod[name] ?? null;
      }
      console.log(JSON.stringify({
        sourceModule: candidate,
        constants,
        defaultModelConfigs: mod.DEFAULT_MODEL_CONFIGS,
      }));
      process.exit(0);
    }
  } catch (error) {
    errors.push({
      candidate,
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

console.error(JSON.stringify({
  error: 'No candidate module exported DEFAULT_MODEL_CONFIGS',
  candidates,
  errors,
}));
process.exit(2);
""".strip()


class GeminiCliModelError(RuntimeError):
    """Raised when the Gemini CLI model registry cannot be discovered."""


@dataclass(frozen=True)
class SourceMetadata:
    """Metadata describing where the Gemini CLI registry came from."""

    cli_path: Path
    bundle_entry: Path
    bundle_dir: Path
    package_dir: Path
    package_version: str
    cli_version: str
    node_path: Path
    source_module: Path
    constants: JsonObject

    def to_json(self) -> JsonObject:
        return {
            "cli_path": str(self.cli_path),
            "bundle_entry": str(self.bundle_entry),
            "bundle_dir": str(self.bundle_dir),
            "package_dir": str(self.package_dir),
            "package_version": self.package_version,
            "cli_version": self.cli_version,
            "node_path": str(self.node_path),
            "source_module": str(self.source_module),
            "constants": self.constants,
        }


@dataclass(frozen=True)
class ModelDefinition:
    """A normalized Gemini CLI model definition."""

    model_id: str
    tier: str | None
    family: str | None
    is_preview: bool
    is_visible: bool
    is_concrete: bool
    features: dict[str, bool]
    display_name: str | None

    def to_json(self) -> JsonObject:
        return {
            "model_id": self.model_id,
            "tier": self.tier,
            "family": self.family,
            "is_preview": self.is_preview,
            "is_visible": self.is_visible,
            "is_concrete": self.is_concrete,
            "features": cast(JsonObject, self.features.copy()),
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class AliasDefinition:
    """A normalized Gemini CLI alias or helper model config."""

    name: str
    extends: str | None
    target_model: str | None
    tier: str | None
    family: str | None
    is_preview: bool | None
    is_visible: bool
    features: dict[str, bool]
    resolution: JsonObject | None
    is_standard: bool

    def to_json(self) -> JsonObject:
        return {
            "name": self.name,
            "extends": self.extends,
            "target_model": self.target_model,
            "tier": self.tier,
            "family": self.family,
            "is_preview": self.is_preview,
            "is_visible": self.is_visible,
            "features": cast(JsonObject, self.features.copy()),
            "resolution": self.resolution,
            "is_standard": self.is_standard,
        }


@dataclass(frozen=True)
class ProbeResult:
    """Result from an explicit Gemini CLI model request."""

    model_id: str
    status: Literal["ok", "failed", "skipped"]
    command: list[str]
    returncode: int | None
    response_text: str | None
    stdout: str | None
    stderr: str | None
    error: str | None

    def to_json(self) -> JsonObject:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "command": cast(list[JsonValue], self.command.copy()),
            "returncode": self.returncode,
            "response_text": self.response_text,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
        }


@dataclass(frozen=True)
class GeminiCliRegistry:
    """Normalized Gemini CLI model registry plus source metadata."""

    source: SourceMetadata
    models: list[ModelDefinition]
    aliases: list[AliasDefinition]

    def display_models(self, include_all: bool = False) -> list[ModelDefinition]:
        if include_all:
            return self.models
        return [
            model for model in self.models if model.is_visible and model.is_concrete
        ]

    def display_aliases(self, include_all: bool = False) -> list[AliasDefinition]:
        if include_all:
            return self.aliases
        return [
            alias
            for alias in self.aliases
            if alias.is_visible or alias.name in STANDARD_ALIAS_NAMES
        ]

    def to_json(self, include_all: bool = False) -> JsonObject:
        return {
            "source": self.source.to_json(),
            "account_availability": {
                "status": "not_checked",
                "note": "CLI registry is local; run probe mode to check account callability.",
            },
            "models": [
                model.to_json()
                for model in self.display_models(include_all=include_all)
            ],
            "aliases": [
                alias.to_json()
                for alias in self.display_aliases(include_all=include_all)
            ],
        }


def load_registry(executable: str = "gemini") -> GeminiCliRegistry:
    """Load the installed Gemini CLI model registry without making model requests."""

    cli_path = locate_executable(executable)
    bundle_entry = resolve_bundle_entry(cli_path)
    package_dir = resolve_package_dir(bundle_entry)
    bundle_dir = package_dir / "bundle"
    if not bundle_dir.is_dir():
        raise GeminiCliModelError(
            f"Gemini CLI bundle directory not found: {bundle_dir}"
        )

    node_path = locate_executable("node")
    package_version = read_package_version(package_dir)
    cli_version = run_gemini_version(cli_path)
    candidates = find_registry_module_candidates(bundle_dir)
    raw_registry = import_default_model_configs(node_path, candidates)

    source_module_value = raw_registry.get("sourceModule")
    if not isinstance(source_module_value, str):
        raise GeminiCliModelError("Node registry probe did not return sourceModule")

    constants = raw_registry.get("constants", {})
    if not isinstance(constants, dict):
        raise GeminiCliModelError("Node registry probe returned invalid constants")

    config = raw_registry.get("defaultModelConfigs")
    if not isinstance(config, dict):
        raise GeminiCliModelError(
            "Node registry probe did not return DEFAULT_MODEL_CONFIGS"
        )

    source = SourceMetadata(
        cli_path=cli_path,
        bundle_entry=bundle_entry,
        bundle_dir=bundle_dir,
        package_dir=package_dir,
        package_version=package_version,
        cli_version=cli_version,
        node_path=node_path,
        source_module=Path(source_module_value),
        constants=cast(JsonObject, constants),
    )
    return normalize_registry(cast(JsonObject, config), source)


def locate_executable(name: str) -> Path:
    executable = shutil.which(name)
    if executable is None:
        raise GeminiCliModelError(f"Required executable not found on PATH: {name}")
    return Path(executable)


def resolve_bundle_entry(cli_path: Path) -> Path:
    try:
        bundle_entry = cli_path.resolve(strict=True)
    except OSError as error:
        raise GeminiCliModelError(
            f"Cannot resolve Gemini CLI path: {cli_path}"
        ) from error
    if not bundle_entry.is_file():
        raise GeminiCliModelError(f"Gemini CLI path is not a file: {bundle_entry}")
    return bundle_entry


def resolve_package_dir(bundle_entry: Path) -> Path:
    for parent in bundle_entry.parents:
        package_json = parent / "package.json"
        if not package_json.is_file():
            continue
        try:
            package_data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise GeminiCliModelError(f"Cannot read {package_json}") from error
        if isinstance(package_data, dict) and package_data.get("name") == (
            "@google/gemini-cli"
        ):
            return parent
    raise GeminiCliModelError(
        f"Could not find @google/gemini-cli package.json above {bundle_entry}"
    )


def read_package_version(package_dir: Path) -> str:
    package_json = package_dir / "package.json"
    try:
        package_data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GeminiCliModelError(f"Cannot read {package_json}") from error
    version = package_data.get("version") if isinstance(package_data, dict) else None
    if not isinstance(version, str):
        raise GeminiCliModelError(f"Missing package version in {package_json}")
    return version


def run_gemini_version(cli_path: Path) -> str:
    result = subprocess.run(
        [str(cli_path), "--version"],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        message = _command_error_message(result)
        raise GeminiCliModelError(f"gemini --version failed: {message}")
    version = result.stdout.strip()
    if not version:
        raise GeminiCliModelError("gemini --version returned empty output")
    return version


def find_registry_module_candidates(bundle_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in sorted(bundle_dir.rglob("*.js")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "DEFAULT_MODEL_CONFIGS" in text:
            candidates.append(path)

    if not candidates:
        raise GeminiCliModelError(
            f"No Gemini CLI bundle module mentions DEFAULT_MODEL_CONFIGS in {bundle_dir}"
        )

    return sorted(candidates, key=_candidate_sort_key)


def import_default_model_configs(node_path: Path, candidates: list[Path]) -> JsonObject:
    result = subprocess.run(
        [
            str(node_path),
            "-e",
            _REGISTRY_EXPORT_SCRIPT,
            *[str(path) for path in candidates],
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise GeminiCliModelError(
            f"Node import probe for DEFAULT_MODEL_CONFIGS failed: {message}"
        )

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise GeminiCliModelError(
            f"Node import probe returned invalid JSON: {result.stdout[:500]}"
        ) from error

    if not isinstance(parsed, dict):
        raise GeminiCliModelError("Node import probe returned non-object JSON")
    return cast(JsonObject, parsed)


def normalize_registry(config: JsonObject, source: SourceMetadata) -> GeminiCliRegistry:
    model_definitions = _object_value(config, "modelDefinitions")
    aliases = _object_value(config, "aliases", required=False)
    model_id_resolutions = _object_value(config, "modelIdResolutions", required=False)

    models = [
        _build_model_definition(model_id, definition, aliases)
        for model_id, definition in model_definitions.items()
    ]
    alias_entries = _build_alias_definitions(
        aliases=aliases,
        model_definitions=model_definitions,
        model_id_resolutions=model_id_resolutions,
        concrete_model_ids={model.model_id for model in models if model.is_concrete},
    )

    return GeminiCliRegistry(source=source, models=models, aliases=alias_entries)


def probe_models(
    registry: GeminiCliRegistry,
    *,
    selected_model: str | None = None,
    limit: int | None = None,
    timeout: int = 120,
) -> list[ProbeResult]:
    """Make explicit Gemini CLI requests for visible concrete models."""

    if selected_model:
        selected = next(
            (
                model
                for model in registry.models
                if model.model_id == selected_model and model.is_concrete
            ),
            None,
        )
        if selected is None:
            raise GeminiCliModelError(
                f"Probe model is not a known concrete Gemini CLI model: {selected_model}"
            )
        models = [selected]
    else:
        models = registry.display_models()

    if limit is not None:
        if limit < 1:
            raise GeminiCliModelError("--limit must be greater than zero")
        models = models[:limit]

    if not models:
        raise GeminiCliModelError("No visible concrete models available to probe")

    return [
        probe_model(registry.source.cli_path, model.model_id, timeout=timeout)
        for model in models
    ]


def probe_model(cli_path: Path, model_id: str, *, timeout: int = 120) -> ProbeResult:
    """Make one minimal Gemini CLI request for a concrete model."""

    command = [
        str(cli_path),
        "-m",
        model_id,
        "-p",
        PROBE_PROMPT,
        "--output-format",
        "json",
        "--approval-mode",
        "plan",
        "-e",
        "none",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        return ProbeResult(
            model_id=model_id,
            status="failed",
            command=command,
            returncode=None,
            response_text=None,
            stdout=_strip_or_none(error.stdout),
            stderr=_strip_or_none(error.stderr),
            error=f"Timed out after {timeout}s",
        )

    stdout = _strip_or_none(result.stdout)
    stderr = _strip_or_none(result.stderr)
    response_text = _extract_response_text(stdout)
    if result.returncode == 0:
        return ProbeResult(
            model_id=model_id,
            status="ok",
            command=command,
            returncode=result.returncode,
            response_text=response_text,
            stdout=stdout,
            stderr=stderr,
            error=None,
        )

    return ProbeResult(
        model_id=model_id,
        status="failed",
        command=command,
        returncode=result.returncode,
        response_text=response_text,
        stdout=stdout,
        stderr=stderr,
        error=_brief_error(stdout=stdout, stderr=stderr, returncode=result.returncode),
    )


def _build_model_definition(
    model_id: str, raw_definition: JsonValue, aliases: JsonObject
) -> ModelDefinition:
    if not isinstance(raw_definition, dict):
        raise GeminiCliModelError(f"Invalid model definition for {model_id}")
    definition = cast(JsonObject, raw_definition)
    alias_definition = aliases.get(model_id)
    direct_alias_target = _target_model(alias_definition)
    is_concrete = direct_alias_target == model_id or _looks_like_model_id(model_id)

    return ModelDefinition(
        model_id=model_id,
        tier=_optional_string(definition.get("tier")),
        family=_optional_string(definition.get("family")),
        is_preview=bool(definition.get("isPreview", False)),
        is_visible=bool(definition.get("isVisible", False)),
        is_concrete=is_concrete,
        features=_feature_flags(definition.get("features")),
        display_name=_optional_string(definition.get("displayName")),
    )


def _build_alias_definitions(
    aliases: JsonObject,
    model_definitions: JsonObject,
    model_id_resolutions: JsonObject,
    concrete_model_ids: set[str],
) -> list[AliasDefinition]:
    names = [
        name
        for name in dict.fromkeys(
            [*aliases.keys(), *model_definitions.keys(), *model_id_resolutions.keys()]
        )
        if name not in concrete_model_ids
    ]

    return [
        _build_alias_definition(name, aliases, model_definitions, model_id_resolutions)
        for name in names
    ]


def _build_alias_definition(
    name: str,
    aliases: JsonObject,
    model_definitions: JsonObject,
    model_id_resolutions: JsonObject,
) -> AliasDefinition:
    raw_alias = aliases.get(name)
    alias = cast(JsonObject, raw_alias) if isinstance(raw_alias, dict) else {}
    raw_model_definition = model_definitions.get(name)
    model_definition = (
        cast(JsonObject, raw_model_definition)
        if isinstance(raw_model_definition, dict)
        else {}
    )
    raw_resolution = model_id_resolutions.get(name)
    resolution = (
        cast(JsonObject, raw_resolution) if isinstance(raw_resolution, dict) else None
    )

    return AliasDefinition(
        name=name,
        extends=_optional_string(alias.get("extends")),
        target_model=_target_model(alias),
        tier=_optional_string(model_definition.get("tier")),
        family=_optional_string(model_definition.get("family")),
        is_preview=_optional_bool(model_definition.get("isPreview")),
        is_visible=bool(model_definition.get("isVisible", False)),
        features=_feature_flags(model_definition.get("features")),
        resolution=resolution,
        is_standard=name in STANDARD_ALIAS_NAMES,
    )


def _object_value(data: JsonObject, key: str, required: bool = True) -> JsonObject:
    value = data.get(key)
    if value is None and not required:
        return {}
    if not isinstance(value, dict):
        raise GeminiCliModelError(f"DEFAULT_MODEL_CONFIGS.{key} is not an object")
    return cast(JsonObject, value)


def _target_model(alias_definition: JsonValue) -> str | None:
    if not isinstance(alias_definition, dict):
        return None
    model_config = alias_definition.get("modelConfig")
    if not isinstance(model_config, dict):
        return None
    model = model_config.get("model")
    return model if isinstance(model, str) else None


def _feature_flags(raw_features: JsonValue) -> dict[str, bool]:
    if not isinstance(raw_features, dict):
        return {}
    return {
        str(name): value
        for name, value in raw_features.items()
        if isinstance(value, bool)
    }


def _optional_string(value: JsonValue) -> str | None:
    return value if isinstance(value, str) else None


def _optional_bool(value: JsonValue) -> bool | None:
    return value if isinstance(value, bool) else None


def _looks_like_model_id(name: str) -> bool:
    return name.startswith(("gemini-", "gemma-"))


def _candidate_sort_key(path: Path) -> tuple[int, str]:
    if path.name.startswith("dist-"):
        return (0, path.name)
    if path.name.startswith("core-"):
        return (1, path.name)
    return (2, path.name)


def _extract_response_text(stdout: str | None) -> str | None:
    if stdout is None:
        return None
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout

    if isinstance(parsed, str):
        return parsed
    if not isinstance(parsed, dict):
        return stdout

    for key in ("response", "text", "content", "result"):
        value = parsed.get(key)
        if isinstance(value, str):
            return value

    return stdout


def _strip_or_none(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    stripped = text.strip()
    return stripped or None


def _brief_error(*, stdout: str | None, stderr: str | None, returncode: int) -> str:
    message = stderr or stdout or f"exit code {returncode}"
    if len(message) <= 500:
        return message
    return f"{message[:497]}..."


def _command_error_message(result: subprocess.CompletedProcess[str]) -> str:
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    if stderr and stdout:
        return f"{stderr}; stdout: {stdout}"
    return stderr or stdout or f"exit code {result.returncode}"
