"""Regression test for the Ariyadhammika YouTube dry-run command path."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_SOURCE = (
    PROJECT_ROOT
    / "output"
    / "transcribed"
    / "english"
    / "2022-04-29 - Endurance and Patience in Practice - Bhikkhu Devamitta.md"
)
BIO_EN = (
    "Āyasmā Ariyadhammika's bio can be found here: "
    "https://sasanarakkha.org/55114/ariyadhammika/"
)
MIN_DESCRIPTION_WORDS = 90
EDITED_TITLE = "Edited Ariyadhammika Upload Title"
EDITED_DESCRIPTION = (
    "Edited description for the upload preview. This text is deliberately written "
    "after metadata generation to prove that human review edits are the source of "
    "truth for export filenames and upload metadata."
)
EDITED_TAGS = "#edited #SBS #sasanarakkha #dhamma"


def _symlink_or_copy(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        return
    try:
        destination.symlink_to(source, target_is_directory=source.is_dir())
    except OSError:
        if source.is_dir():
            shutil.copytree(
                source,
                destination,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
        else:
            shutil.copy2(source, destination)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_command_shims(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True)
    python = shlex.quote(sys.executable)
    _write_executable(
        bin_dir / "uv",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'if [ "${1:-}" = "run" ]; then shift; fi',
                'if [ "${1:-}" = "python" ]; then',
                "  shift",
                f'  exec {python} "$@"',
                "fi",
                'exec "$@"',
                "",
            ]
        ),
    )
    _write_executable(
        bin_dir / "caffeinate",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'while [ "$#" -gt 0 ] && [ "${1#-}" != "$1" ]; do shift; done',
                'exec "$@"',
                "",
            ]
        ),
    )
    _write_executable(
        bin_dir / "nice",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'if [ "${1:-}" = "-n" ]; then shift 2; fi',
                'exec "$@"',
                "",
            ]
        ),
    )


def _read_dotenv_value(key: str) -> str:
    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return ""
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != key:
            continue
        return value.strip().strip("\"'")
    return ""


def _write_project_env(project: Path) -> None:
    lines = [
        "PROVIDER=openrouter",
        "IMAGE_PROVIDER=openrouter",
        f'BIO_EN="{BIO_EN}"',
    ]
    openrouter_key = _read_dotenv_value("OPENROUTER_API_KEY") or os.environ.get(
        "OPENROUTER_API_KEY", ""
    )
    if openrouter_key:
        lines.append(f'OPENROUTER_API_KEY="{openrouter_key}"')
    (project / ".env").write_text("\n".join([*lines, ""]), encoding="utf-8")


def _prepare_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "ardmk_project"
    project.mkdir()
    for directory in ("input", "output", "reviews", "temp"):
        (project / directory).mkdir()

    _symlink_or_copy(PROJECT_ROOT / "yt_run.sh", project / "yt_run.sh")
    _symlink_or_copy(PROJECT_ROOT / "scripts", project / "scripts")
    _symlink_or_copy(PROJECT_ROOT / "tools", project / "tools")
    _symlink_or_copy(PROJECT_ROOT / "pyproject.toml", project / "pyproject.toml")
    _symlink_or_copy(PROJECT_ROOT / "uv.lock", project / "uv.lock")

    _write_project_env(project)
    for filename in ("test.mp4", "test.wav", "test.png"):
        (project / "input" / filename).write_bytes(b"dry-run fixture")

    bin_dir = tmp_path / "bin"
    _write_command_shims(bin_dir)
    return project, bin_dir


def _run_command(
    project: Path,
    bin_dir: Path,
    args: list[str],
    input_text: str = "",
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "PROVIDER": "openrouter",
        "IMAGE_PROVIDER": "openrouter",
        "BIO_EN": BIO_EN,
    }
    openrouter_key = _read_dotenv_value("OPENROUTER_API_KEY") or os.environ.get(
        "OPENROUTER_API_KEY", ""
    )
    if openrouter_key:
        env["OPENROUTER_API_KEY"] = openrouter_key
    return subprocess.run(
        args,
        cwd=project,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _run_yt_run(project: Path, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    return _run_command(
        project,
        bin_dir,
        [
            str(project / "yt_run.sh"),
            "--name",
            "Ariyadhammika Bhikkhu",
            "--video-mode",
            "--dry-run",
            "--limit",
            "3",
        ],
        input_text="\n",
        timeout=120,
    )


def _run_python(
    project: Path,
    bin_dir: Path,
    script: str,
    args: list[str],
    input_text: str = "",
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return _run_command(
        project,
        bin_dir,
        ["uv", "run", "python", script, *args],
        input_text=input_text,
        timeout=timeout,
    )


def _run_metadata_generation(
    project: Path,
    bin_dir: Path,
    metadata_log: Path,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        [
            "from pathlib import Path",
            "from scripts.yt_metadata import process_files",
            "process_files(",
            "    [Path('output/transcribed/test.md')],",
            "    'en',",
            "    'reviews/english_review.md',",
            "    '',",
            "    speaker_name='Ariyadhammika Bhikkhu',",
            "    media='video',",
            "    bio_link=" + repr(BIO_EN) + ",",
            "    playlist_overview='Meditation, Personal',",
            f"    created_log=Path({str(metadata_log)!r}),",
            ")",
            "",
        ]
    )
    return _run_command(
        project,
        bin_dir,
        ["uv", "run", "python", "-c", code],
        timeout=180,
    )


def _assert_yt_ardmk_command_matches_tested_command() -> None:
    wrapper = (PROJECT_ROOT / "scripts" / "cl" / "yt-ardmk").read_text(encoding="utf-8")

    assert (
        "echo 'Running: ./yt_run.sh --name \"Ariyadhammika Bhikkhu\" --video-mode'"
        in wrapper
    )
    assert './yt_run.sh --name "Ariyadhammika Bhikkhu" --video-mode' in wrapper


def _write_real_media_fixtures(project: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.fail("ffmpeg is required for the realistic Ariyadhammika test")

    commands = [
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "1",
            "input/test.wav",
        ],
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=1280x720:r=25",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "1",
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "input/test.mp4",
        ],
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=1280x720",
            "-frames:v",
            "1",
            "input/test.png",
        ],
    ]
    for command in commands:
        result = subprocess.run(
            command,
            cwd=project,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr


def _write_transcript_excerpt(project: Path, max_minutes: float = 5.0) -> None:
    assert TRANSCRIPT_SOURCE.exists(), f"missing source transcript: {TRANSCRIPT_SOURCE}"
    excerpt_lines: list[str] = []
    for line in TRANSCRIPT_SOURCE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\[(\d+(?:\.\d+)?)\]", line)
        if match and float(match.group(1)) > max_minutes:
            break
        excerpt_lines.append(line)

    transcript_path = project / "output" / "transcribed" / "test.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        "\n".join(excerpt_lines).strip() + "\n",
        encoding="utf-8",
    )


def _review_field(content: str, field: str) -> str:
    pattern = rf"\*\*{re.escape(field)}:\*\*\s*(.*?)(?=\n\*\*|\n---|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    assert match, f"missing review field: {field}"
    return match.group(1).strip()


def _replace_review_field(content: str, field: str, value: str) -> str:
    pattern = rf"(\*\*{re.escape(field)}:\*\*\s*)(.*?)(?=\n\*\*|\n---|\Z)"
    replacement = rf"\g<1>{value}"
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.DOTALL)
    assert count == 1, f"missing review field: {field}"
    return updated


def _edit_and_approve_review(review_path: Path) -> str:
    content = review_path.read_text(encoding="utf-8")
    content = content.replace(
        "**Recording Date:** \n",
        "**Recording Date:** 01-01-2000\n",
    )
    content = content.replace("**Approved:** no\n", "**Approved:** yes\n")
    content = _replace_review_field(content, "Suggested Title", EDITED_TITLE)
    content = _replace_review_field(
        content, "Suggested Description", EDITED_DESCRIPTION
    )
    content = _replace_review_field(content, "Suggested Tags", EDITED_TAGS)
    review_path.write_text(content, encoding="utf-8")
    return content


def _diagnostic_report(
    *,
    dry_run_output: str = "",
    ingest_output: str = "",
    metadata_output: str = "",
    generated_review: str = "",
    edited_review: str = "",
    export_output: str = "",
    upload_output: str = "",
) -> str:
    sections = {
        "DRY RUN OUTPUT": dry_run_output,
        "INGEST OUTPUT": ingest_output,
        "METADATA OUTPUT": metadata_output,
        "GENERATED REVIEW": generated_review,
        "EDITED REVIEW": edited_review,
        "EXPORT OUTPUT": export_output,
        "UPLOAD OUTPUT": upload_output,
    }
    return "\n\n".join(
        f"===== {label} =====\n{body.rstrip()}"
        for label, body in sections.items()
        if body
    )


def _assert_or_report(condition: bool, message: str, diagnostic: str) -> None:
    if not condition:
        pytest.fail(f"{message}\n\n{diagnostic}")


def test_yt_ardmk_validates_ariyadhammika_video_dry_run_trace(
    tmp_path: Path,
) -> None:
    _assert_yt_ardmk_command_matches_tested_command()
    project, bin_dir = _prepare_project(tmp_path)

    result = _run_yt_run(project, bin_dir)
    output = result.stdout + result.stderr
    diagnostic = _diagnostic_report(dry_run_output=output)

    _assert_or_report(result.returncode == 0, "dry-run command failed", diagnostic)
    compact_output = " ".join(output.split())
    criteria = {
        "input folder was scanned": "Processing: input" in compact_output,
        "mp4 routed to video": "→ video: output/video/test.mp4" in compact_output,
        "wav provides mp3 audio": "→ audio: provided by input/test.wav"
        in compact_output,
        "wav converts to mp3": "input/test.wav → output/audio/test.mp3"
        in compact_output,
        "png converts to thumbnail jpg": "input/test.png → output/thumbnails/test.jpg"
        in compact_output,
        "png converts to cover jpg": "input/test.png → output/covers/test.jpg"
        in compact_output,
        "wav was not skipped": "Skipping test.wav (mp3 exists)" not in compact_output,
        "upload file is printed": "File: output/video/2000-01-01 - [DRY_RUN] test.mp4"
        in compact_output,
        "dry-run title is printed": "Title: [DRY_RUN] test" in compact_output,
        "bio is printed": BIO_EN in compact_output,
        "pipeline completed": "PIPELINE COMPLETE." in output,
    }
    failed = [label for label, ok in criteria.items() if not ok]
    _assert_or_report(not failed, f"dry-run criteria failed: {failed}", diagnostic)


def test_yt_ardmk_generates_real_metadata_and_upload_preview(
    tmp_path: Path,
) -> None:
    _assert_yt_ardmk_command_matches_tested_command()
    project, bin_dir = _prepare_project(tmp_path)
    for fixture in (project / "input").iterdir():
        fixture.unlink()
    _write_real_media_fixtures(project)
    _write_transcript_excerpt(project)

    ingest = _run_python(
        project,
        bin_dir,
        "scripts/yt_ingest_unified.py",
        ["--limit", "3"],
        timeout=120,
    )
    ingest_output = ingest.stdout + ingest.stderr
    diagnostic = _diagnostic_report(ingest_output=ingest_output)
    _assert_or_report(ingest.returncode == 0, "ingest failed", diagnostic)
    _assert_or_report(
        (project / "output" / "audio" / "test.mp3").exists(),
        "wav did not convert to output/audio/test.mp3",
        diagnostic,
    )
    _assert_or_report(
        (project / "output" / "video" / "test.mp4").exists(),
        "mp4 did not route to output/video/test.mp4",
        diagnostic,
    )
    _assert_or_report(
        (project / "output" / "thumbnails" / "test.jpg").exists(),
        "png did not convert to output/thumbnails/test.jpg",
        diagnostic,
    )
    _assert_or_report(
        (project / "output" / "covers" / "test.jpg").exists(),
        "png did not convert to output/covers/test.jpg",
        diagnostic,
    )

    metadata_log = project / "temp" / "metadata.log"
    metadata = _run_metadata_generation(
        project,
        bin_dir,
        metadata_log,
    )
    metadata_output = metadata.stdout + metadata.stderr
    diagnostic = _diagnostic_report(
        ingest_output=ingest_output,
        metadata_output=metadata_output,
    )
    _assert_or_report(
        metadata.returncode == 0, "metadata generation failed", diagnostic
    )

    review_path = project / "reviews" / "english_review.md"
    generated_review = review_path.read_text(encoding="utf-8")
    title = _review_field(generated_review, "Suggested Title")
    description = _review_field(generated_review, "Suggested Description")
    tags = _review_field(generated_review, "Suggested Tags")
    diagnostic = _diagnostic_report(
        ingest_output=ingest_output,
        metadata_output=metadata_output,
        generated_review=generated_review,
    )

    generated_criteria = {
        "metadata is real, not dry-run": "[DRY_RUN]" not in generated_review,
        "generated title exists": bool(title),
        "generated description is big enough": len(description.split())
        >= MIN_DESCRIPTION_WORDS,
        "generated tags exist": tags.startswith("#"),
        "generated tags include SBS": "#SBS" in tags.split(),
        "generated title has no speaker name": "Ariyadhammika" not in title,
        "bio is correct": BIO_EN in description,
    }
    failed = [label for label, ok in generated_criteria.items() if not ok]
    _assert_or_report(
        not failed,
        f"generated metadata criteria failed: {failed}",
        diagnostic,
    )

    edited_review = _edit_and_approve_review(review_path)
    export_log = project / "temp" / "export.log"
    export = _run_python(
        project,
        bin_dir,
        "scripts/yt_export.py",
        [
            "--lang",
            "en",
            "--folder",
            "",
            "--name",
            "Ariyadhammika Bhikkhu",
            "--video-mode",
            "--created-log",
            str(export_log),
            "--source-log",
            str(metadata_log),
        ],
        timeout=120,
    )
    export_output = export.stdout + export.stderr
    diagnostic = _diagnostic_report(
        ingest_output=ingest_output,
        metadata_output=metadata_output,
        generated_review=generated_review,
        edited_review=edited_review,
        export_output=export_output,
    )
    _assert_or_report(export.returncode == 0, "export failed", diagnostic)
    edited_video = project / "output" / "video" / f"2000-01-01 - {EDITED_TITLE}.mp4"
    generated_video = project / "output" / "video" / f"2000-01-01 - {title}.mp4"
    _assert_or_report(
        edited_video.exists(),
        "export did not rename video according to edited title",
        diagnostic,
    )
    _assert_or_report(
        not generated_video.exists(),
        "export used generated title instead of edited title",
        diagnostic,
    )

    upload = _run_python(
        project,
        bin_dir,
        "scripts/yt_upload.py",
        [
            "--lang",
            "en",
            "--folder",
            "",
            "--dry-run",
            "--files-from-log",
            str(export_log),
            "--name",
            "Ariyadhammika Bhikkhu",
        ],
        input_text="\n",
        timeout=120,
    )
    upload_output = upload.stdout + upload.stderr
    diagnostic = _diagnostic_report(
        ingest_output=ingest_output,
        metadata_output=metadata_output,
        generated_review=generated_review,
        edited_review=edited_review,
        export_output=export_output,
        upload_output=upload_output,
    )

    _assert_or_report(upload.returncode == 0, "upload preview failed", diagnostic)
    compact_upload = " ".join(upload_output.split())
    upload_criteria = {
        "one upload queued": "1 video(s) queued for YouTube upload." in compact_upload,
        "upload file uses edited title": (
            f"File: output/video/2000-01-01 - {EDITED_TITLE}.mp4" in compact_upload
        ),
        "upload title uses edited title": f"Title: {EDITED_TITLE}" in compact_upload,
        "upload description uses edited description": (
            " ".join(EDITED_DESCRIPTION.split()) in compact_upload
        ),
        "upload tags use edited tags": "edited, SBS, sasanarakkha, dhamma"
        in compact_upload,
        "upload bio is correct": BIO_EN in compact_upload,
        "upload no longer uses generated title": f"Title: {title}"
        not in compact_upload,
        "upload has expected privacy": "Privacy status: private (scheduled)"
        in compact_upload,
    }
    failed = [label for label, ok in upload_criteria.items() if not ok]
    _assert_or_report(
        not failed,
        f"upload metadata criteria failed: {failed}",
        diagnostic,
    )
