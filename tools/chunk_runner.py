"""Shared chunked file-processing runner with resume and retry support."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from tools import printer as _p
from tools.incremental import finalize_temp, get_temp_path, load_temp, save_temp

pr = _p.printer

Chunker = Callable[[str], list[str]]
GenerateFn = Callable[[str, Path], str]
ChunkValidator = Callable[[str, str, Path, int], bool]
ResultTransformer = Callable[[str, str, Path, int], str]

FileStatus = Literal["success", "failed", "skipped", "empty"]

EXIT_OK = 0
EXIT_HARD_FAILURE = 1
EXIT_PARTIAL = 2

ATTEMPTS_PER_CHUNK = 3
RETRY_ROUNDS = 2


@dataclass(frozen=True)
class RunnerConfig:
    input_dir: Path
    output_dir: Path
    chunker: Chunker
    generate: GenerateFn
    label: str
    validator: ChunkValidator | None = None
    result_transformer: ResultTransformer | None = None
    pacing_seconds: float = 0.0


@dataclass(frozen=True)
class QueueItem:
    input_path: Path
    output_path: Path


@dataclass(frozen=True)
class DiscoveryResult:
    queue: list[QueueItem]
    skipped_existing: int
    discovered: int


@dataclass(frozen=True)
class FileRunResult:
    input_path: Path
    output_path: Path
    status: FileStatus
    failed_chunks: list[int] = field(default_factory=list)
    message: str = ""


@dataclass(frozen=True)
class RunResult:
    files: list[FileRunResult]
    skipped_existing: int = 0
    discovered: int = 0
    hard_error: str | None = None

    @property
    def exit_code(self) -> int:
        if self.hard_error is not None:
            return EXIT_HARD_FAILURE
        if any(result.status == "failed" for result in self.files):
            return EXIT_PARTIAL
        return EXIT_OK


class RunnerError(Exception):
    """Raised when runner input selection cannot be resolved."""


def discover_files(
    config: RunnerConfig,
    file: str | Path | None = None,
    folder: str | Path | None = None,
    limit: int | None = None,
) -> DiscoveryResult:
    """Build the unprocessed file queue for a runner configuration."""
    input_dir = config.input_dir
    output_dir = config.output_dir

    if file is not None and folder is not None:
        raise RunnerError("Use either a file argument or --folder, not both.")

    if file is not None:
        file_path = Path(file)
        if not file_path.is_absolute() and not file_path.exists():
            file_path = input_dir / file_path
        if not file_path.exists():
            raise RunnerError(f"File not found: {file_path}")
        md_files = _markdown_files_from_path(file_path)
    elif folder is not None:
        folder_path = input_dir / Path(folder)
        if not folder_path.exists():
            raise RunnerError(f"Folder not found: {folder_path}")
        md_files = _markdown_files_from_path(folder_path)
    else:
        md_files = _sorted_markdown_files(input_dir)

    queue: list[QueueItem] = []
    skipped_existing = 0
    for input_path in md_files:
        output_path = mirror_output_path(input_path, input_dir, output_dir)
        if output_path.exists():
            skipped_existing += 1
            continue
        queue.append(QueueItem(input_path=input_path, output_path=output_path))

    if limit is not None:
        queue = queue[:limit]

    return DiscoveryResult(
        queue=queue,
        skipped_existing=skipped_existing,
        discovered=len(md_files),
    )


def run(
    config: RunnerConfig,
    file: str | Path | None = None,
    folder: str | Path | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> RunResult:
    """Run a chunked file-processing stage and return per-file results."""
    try:
        discovery = discover_files(
            config=config,
            file=file,
            folder=folder,
            limit=limit,
        )
    except RunnerError as exc:
        pr.red(str(exc))
        return RunResult(files=[], hard_error=str(exc))

    if discovery.skipped_existing:
        pr.green(
            f"{discovery.skipped_existing} already {config.label}, "
            f"{len(discovery.queue)} to process"
        )

    if not discovery.queue:
        pr.green("Nothing to process.")
        return RunResult(
            files=[],
            skipped_existing=discovery.skipped_existing,
            discovered=discovery.discovered,
        )

    if dry_run:
        for item in discovery.queue:
            pr.green(f"{item.input_path} -> {item.output_path}")
        return RunResult(
            files=[
                FileRunResult(
                    input_path=item.input_path,
                    output_path=item.output_path,
                    status="skipped",
                    message="dry run",
                )
                for item in discovery.queue
            ],
            skipped_existing=discovery.skipped_existing,
            discovered=discovery.discovered,
        )

    pr.green(f"Processing {len(discovery.queue)} file(s)")

    results: list[FileRunResult] = []
    for item in discovery.queue:
        results.append(_run_file(config, item))

    _print_summary(results, discovery.skipped_existing)
    return RunResult(
        files=results,
        skipped_existing=discovery.skipped_existing,
        discovered=discovery.discovered,
    )


def mirror_output_path(input_path: Path, input_dir: Path, output_dir: Path) -> Path:
    """Mirror an input file path into the output tree."""
    try:
        relative_path = input_path.relative_to(input_dir)
    except ValueError:
        return output_dir / input_path.name
    return output_dir / relative_path


def _markdown_files_from_path(path: Path) -> list[Path]:
    if path.is_dir():
        return _sorted_markdown_files(path)
    if path.suffix.lower() != ".md":
        raise RunnerError(f"Expected a .md file: {path}")
    return [path]


def _sorted_markdown_files(path: Path) -> list[Path]:
    return sorted(path.rglob("*.md"), key=lambda item: str(item).lower())


def _run_file(config: RunnerConfig, item: QueueItem) -> FileRunResult:
    pr.green(f"{config.label.capitalize()} '{item.input_path.name}'")
    pr.bip()

    text = item.input_path.read_text(encoding="utf-8")
    if not text.strip():
        pr.no("empty")
        return FileRunResult(
            input_path=item.input_path,
            output_path=item.output_path,
            status="empty",
            message="empty input",
        )

    chunks = config.chunker(text)
    if not chunks:
        pr.no("no chunks")
        return FileRunResult(
            input_path=item.input_path,
            output_path=item.output_path,
            status="empty",
            message="chunker returned no chunks",
        )

    temp_path = get_temp_path(item.output_path)
    saved = _normalize_saved(load_temp(temp_path), len(chunks))

    if 0 < len(saved) < len(chunks):
        pr.green(f"  Resuming from chunk {len(saved) + 1}/{len(chunks)}")

    for index in range(len(saved), len(chunks)):
        result = _process_chunk(config, chunks[index], item.input_path, index)
        saved.append(result)
        save_temp(temp_path, saved)
        _pace(config)

    for retry_round in range(RETRY_ROUNDS):
        failed_indices = _failed_indices(saved)
        if not failed_indices:
            break

        pr.amber(f"  Retry round {retry_round + 1}: {len(failed_indices)} chunk(s)")
        for index in failed_indices:
            result = _process_chunk(config, chunks[index], item.input_path, index)
            saved[index] = result
            save_temp(temp_path, saved)
            _pace(config)

    failed_indices = _failed_indices(saved)
    if failed_indices:
        pr.no(f"{len(failed_indices)} failed")
        return FileRunResult(
            input_path=item.input_path,
            output_path=item.output_path,
            status="failed",
            failed_chunks=failed_indices,
            message="chunks failed after retries",
        )

    output_text = "\n\n".join(result for result in saved if result)
    item.output_path.parent.mkdir(parents=True, exist_ok=True)
    item.output_path.write_text(output_text, encoding="utf-8")
    finalize_temp(temp_path)
    pr.yes(f"saved -> {item.output_path}")
    return FileRunResult(
        input_path=item.input_path,
        output_path=item.output_path,
        status="success",
    )


def _process_chunk(
    config: RunnerConfig,
    chunk: str,
    file_path: Path,
    index: int,
) -> str | None:
    for attempt in range(1, ATTEMPTS_PER_CHUNK + 1):
        try:
            generated = config.generate(chunk, file_path)
            result = generated.strip()
            if config.result_transformer is not None:
                result = config.result_transformer(chunk, generated, file_path, index)
            if config.validator is not None and not config.validator(
                chunk,
                result,
                file_path,
                index,
            ):
                raise ChunkValidationError("chunk validation failed")
            return result.strip()
        except Exception as exc:
            pr.amber(
                f"  Chunk {index + 1} attempt {attempt}/{ATTEMPTS_PER_CHUNK} "
                f"failed: {exc}"
            )
    return None


def _normalize_saved(saved: list[object], chunk_count: int) -> list[str | None]:
    normalized: list[str | None] = []
    for item in saved[:chunk_count]:
        if item is None:
            normalized.append(None)
        elif isinstance(item, str):
            normalized.append(item)
        else:
            normalized.append(str(item))
    return normalized


def _failed_indices(saved: list[str | None]) -> list[int]:
    return [index for index, result in enumerate(saved) if result is None]


def _pace(config: RunnerConfig) -> None:
    if config.pacing_seconds > 0:
        time.sleep(config.pacing_seconds)


def _print_summary(results: list[FileRunResult], skipped_existing: int) -> None:
    succeeded = sum(result.status == "success" for result in results)
    failed = sum(result.status == "failed" for result in results)
    empty = sum(result.status == "empty" for result in results)
    dry_skipped = sum(result.status == "skipped" for result in results)

    pr.summary("succeeded", succeeded)
    pr.summary("failed", failed)
    pr.summary("skipped", skipped_existing + empty + dry_skipped)


class ChunkValidationError(Exception):
    """Raised internally when generated chunk output fails validation."""
