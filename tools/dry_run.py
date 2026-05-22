"""Shared utilities for pipeline dry-run mode: stub creation, cleanup tracking, flag detection."""

from pathlib import Path

DRY_RUN_CLEANUP_LOG = Path("temp/.dry_run_cleanup")
DRY_RUN_ACTIVE_FLAG = Path("temp/.dry_run_active")


def is_pipeline_dry_run() -> bool:
    """True when yt_run.sh --dry-run [stub] activated this pipeline run."""
    return DRY_RUN_ACTIVE_FLAG.exists()


def log_stub(path: Path) -> None:
    """Register a path in the cleanup log without creating it."""
    DRY_RUN_CLEANUP_LOG.parent.mkdir(exist_ok=True)
    with DRY_RUN_CLEANUP_LOG.open("a", encoding="utf-8") as fh:
        fh.write(str(path) + "\n")


def create_stub(path: Path) -> None:
    """Create a zero-byte stub file and register it for cleanup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    log_stub(path)


def is_stub(path: Path) -> bool:
    """Returns True if path exists and is zero-byte (a dry-run stub)."""
    return path.exists() and path.stat().st_size == 0
