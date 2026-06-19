"""Tests placement of provider preflight calls in pipeline wrappers."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _prepare_fake_runner(tmp_path: Path) -> dict[str, str]:
    shutil.copy2(PROJECT_ROOT / "yt_run.sh", tmp_path / "yt_run.sh")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "caffeinate",
        "#!/bin/sh\nexit 0\n",
    )
    _write_executable(
        bin_dir / "uv",
        """#!/bin/sh
case " $* " in
  *" scripts/check_keys.py "*) touch "$SENTINEL_DIR/preflight"; exit 0 ;;
  *" scripts/yt_metadata.py "*) touch "$SENTINEL_DIR/metadata"; exit "${METADATA_STATUS:-0}" ;;
  *" scripts/yt_image_gen.py "*) touch "$SENTINEL_DIR/image"; exit "${IMAGE_STATUS:-0}" ;;
  *) exit 0 ;;
esac
""",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["SENTINEL_DIR"] = str(tmp_path)
    return env


def _prepare_fake_extract_runner(tmp_path: Path) -> dict[str, str]:
    shutil.copy2(PROJECT_ROOT / "extract_run.sh", tmp_path / "extract_run.sh")
    (tmp_path / ".env").write_text("PROVIDER=openrouter\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "caffeinate",
        """#!/bin/sh
if [ "$1" = "-i" ]; then
  shift
fi
"$@"
""",
    )
    _write_executable(
        bin_dir / "uv",
        """#!/bin/sh
append() { echo "$1" >> "$SENTINEL_DIR/order"; }
case " $* " in
  *" scripts/transcribe.py "*) append transcribe; exit 0 ;;
  *" scripts/check_keys.py "*) append preflight; exit 0 ;;
  *" scripts/correct_pali.py "*) append correct; exit "${CORRECT_STATUS:-0}" ;;
  *" scripts/extract_dhamma.py "*) append extract; exit "${EXTRACT_STATUS:-0}" ;;
  *" scripts/polish_extract.py "*) append polish; exit "${POLISH_STATUS:-0}" ;;
  *" scripts/check_privacy.py "*) append privacy; touch "$SENTINEL_DIR/privacy"; exit "${PRIVACY_STATUS:-0}" ;;
  *" scripts/consolidate.py "*) append consolidate; touch "$SENTINEL_DIR/consolidate"; exit 0 ;;
  *) append other; exit 0 ;;
esac
""",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["SENTINEL_DIR"] = str(tmp_path)
    return env


def test_yt_run_has_no_automatic_provider_preflights() -> None:
    script = _read("yt_run.sh")
    assert "scripts/check_keys.py --text" not in script
    assert "scripts/check_keys.py --image" not in script


def test_extract_run_runs_correction_without_preflight(
    tmp_path: Path,
) -> None:
    env = _prepare_fake_extract_runner(tmp_path)

    result = subprocess.run(
        ["bash", "extract_run.sh", "--from", "transcribe"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    order = (tmp_path / "order").read_text(encoding="utf-8").splitlines()

    assert result.returncode == 0
    assert "preflight" not in order
    assert order[:2] == ["transcribe", "correct"]


def test_extract_run_stage_failure_stops_downstream_work(tmp_path: Path) -> None:
    env = _prepare_fake_extract_runner(tmp_path)
    env["CORRECT_STATUS"] = "42"

    result = subprocess.run(
        ["bash", "extract_run.sh", "--from", "transcribe"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    order = (tmp_path / "order").read_text(encoding="utf-8").splitlines()

    assert result.returncode == 42
    assert order == ["transcribe", "correct"]


@pytest.mark.parametrize(
    ("status_var", "expected_order"),
    [
        ("CORRECT_STATUS", ["transcribe", "correct"]),
        ("EXTRACT_STATUS", ["transcribe", "correct", "extract"]),
        ("POLISH_STATUS", ["transcribe", "correct", "extract", "polish"]),
    ],
)
def test_extract_run_llm_partial_status_stops_downstream_work(
    tmp_path: Path,
    status_var: str,
    expected_order: list[str],
) -> None:
    env = _prepare_fake_extract_runner(tmp_path)
    env[status_var] = "2"

    result = subprocess.run(
        ["bash", "extract_run.sh", "--from", "transcribe"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    order = (tmp_path / "order").read_text(encoding="utf-8").splitlines()

    assert result.returncode == 2
    assert order == expected_order


def test_extract_run_from_consolidate_runs_privacy_then_consolidate(
    tmp_path: Path,
) -> None:
    env = _prepare_fake_extract_runner(tmp_path)

    result = subprocess.run(
        ["bash", "extract_run.sh", "--from", "consolidate"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    order = (tmp_path / "order").read_text(encoding="utf-8").splitlines()

    assert result.returncode == 0
    assert order == ["privacy", "consolidate"]
    assert (tmp_path / "privacy").exists()
    assert (tmp_path / "consolidate").exists()


def test_extract_run_partial_stage_warns_and_continues(tmp_path: Path) -> None:
    env = _prepare_fake_extract_runner(tmp_path)
    env["PRIVACY_STATUS"] = "2"

    result = subprocess.run(
        ["bash", "extract_run.sh", "--from", "consolidate"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    order = (tmp_path / "order").read_text(encoding="utf-8").splitlines()

    assert result.returncode == 0
    assert order == ["privacy", "consolidate"]
    assert "completed with partial failures" in result.stdout
    assert (tmp_path / "consolidate").exists()


def test_yt_run_failed_metadata_stage_stops_before_image_generation(
    tmp_path: Path,
) -> None:
    env = _prepare_fake_runner(tmp_path)
    env["METADATA_STATUS"] = "42"

    result = subprocess.run(
        ["bash", "yt_run.sh", "--lang", "en"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 42
    assert (tmp_path / "metadata").exists()
    assert not (tmp_path / "preflight").exists()
    assert not (tmp_path / "image").exists()


def test_yt_run_failed_image_stage_returns_stage_status(
    tmp_path: Path,
) -> None:
    env = _prepare_fake_runner(tmp_path)
    env["IMAGE_STATUS"] = "42"

    result = subprocess.run(
        ["bash", "yt_run.sh", "--lang", "en"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 42
    assert (tmp_path / "metadata").exists()
    assert not (tmp_path / "preflight").exists()
    assert (tmp_path / "image").exists()
