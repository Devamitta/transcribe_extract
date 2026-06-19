"""Tests placement of provider preflight calls in pipeline wrappers."""

import os
import shutil
import stat
import subprocess
from pathlib import Path


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
TEXT_STATUS="${TEXT_PREFLIGHT_STATUS:-0}"
IMAGE_STATUS="${IMAGE_PREFLIGHT_STATUS:-0}"
case " $* " in
  *" scripts/check_keys.py --text "*) exit "$TEXT_STATUS" ;;
  *" scripts/check_keys.py --image "*) exit "$IMAGE_STATUS" ;;
  *" scripts/yt_metadata.py "*) touch "$SENTINEL_DIR/metadata"; exit 0 ;;
  *" scripts/yt_image_gen.py "*) touch "$SENTINEL_DIR/image"; exit 0 ;;
  *) exit 0 ;;
esac
""",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["SENTINEL_DIR"] = str(tmp_path)
    return env


def test_yt_run_text_preflight_is_before_metadata_and_skips_dry_run() -> None:
    script = _read("yt_run.sh")
    preflight = "uv run python scripts/check_keys.py --text"
    metadata = "uv run python scripts/yt_metadata.py"

    assert script.index(preflight) < script.index(metadata)
    assert (
        'if [ "$DRY_RUN" -eq 0 ]; then\n'
        '    echo "→ Starting: check_keys.py --text"\n'
        "    uv run python scripts/check_keys.py --text\n"
        "  fi\n"
        '  echo "→ Starting: yt_metadata.py"'
    ) in script


def test_yt_run_image_preflight_is_before_thumbnail_generation() -> None:
    script = _read("yt_run.sh")
    preflight = "uv run python scripts/check_keys.py --image"
    image_gen = "uv run python scripts/yt_image_gen.py"

    assert script.index(preflight) < script.index(image_gen)
    assert (
        'if [ "$DRY_RUN" -eq 0 ]; then\n'
        '      echo "→ Starting: check_keys.py --image"\n'
        "      uv run python scripts/check_keys.py --image\n"
        "    fi\n"
        '    echo "→ Starting: yt_image_gen.py"'
    ) in script


def test_extract_run_preflight_is_after_transcription_before_correction() -> None:
    script = _read("extract_run.sh")
    transcribe = "uv run python scripts/transcribe.py"
    preflight = "uv run python scripts/check_keys.py --text"
    correct_pali = "uv run python scripts/correct_pali.py"

    assert script.index(transcribe) < script.index(preflight)
    assert script.index(preflight) < script.index(correct_pali)


def test_yt_run_failed_text_preflight_stops_before_metadata(tmp_path: Path) -> None:
    env = _prepare_fake_runner(tmp_path)
    env["TEXT_PREFLIGHT_STATUS"] = "42"
    env["IMAGE_PREFLIGHT_STATUS"] = "0"

    result = subprocess.run(
        ["bash", "yt_run.sh", "--lang", "en"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 42
    assert not (tmp_path / "metadata").exists()


def test_yt_run_failed_image_preflight_stops_before_image_generation(
    tmp_path: Path,
) -> None:
    env = _prepare_fake_runner(tmp_path)
    env["TEXT_PREFLIGHT_STATUS"] = "0"
    env["IMAGE_PREFLIGHT_STATUS"] = "42"

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
    assert not (tmp_path / "image").exists()
