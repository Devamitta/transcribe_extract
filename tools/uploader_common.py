"""Shared utilities for YouTube and Google Drive upload scripts."""

import json
import pickle
import re
import ssl
import time as time_module
import unicodedata
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tools.printer import printer as pr

UPLOAD_CHUNK_SIZE_BYTES = 32 * 1024 * 1024


class ResumableUploadStatus(Protocol):
    """Progress status returned by googleapiclient resumable upload chunks."""

    resumable_progress: int
    total_size: int | None

    def progress(self) -> float:
        """Return the completed upload fraction from 0.0 to 1.0."""
        ...


class ResumableUploadRequest(Protocol):
    """Request object returned by googleapiclient resumable upload methods."""

    def next_chunk(self) -> tuple[ResumableUploadStatus | None, dict[str, Any] | None]:
        """Upload the next chunk and return progress plus the final response."""
        ...


def execute_resumable_upload(
    request: ResumableUploadRequest,
    progress_label: str,
    progress_output: Callable[[str], None] = pr.white,
    show_speed: bool = False,
    clock: Callable[[], float] = monotonic,
    max_retries: int = 5,
) -> dict[str, Any]:
    """Run a resumable upload request and print percentage progress.

    Automatically retries on transient network/SSL errors with exponential
    backoff (5s, 10s, 20s, 40s, 80s).  Resumable uploads track progress
    server-side, so retrying next_chunk() safely resumes where it left off.
    """
    response: dict[str, Any] | None = None
    last_percent = -1
    last_uploaded_bytes = 0
    last_sample_time = clock()
    last_speed_bytes_per_second: float | None = None
    total_upload_size: int | None = None
    retries = 0
    delay = 5.0

    while response is None:
        try:
            status, response = request.next_chunk()
        except (
            ssl.SSLError,
            ConnectionError,
            ConnectionResetError,
            TimeoutError,
            OSError,
        ) as e:
            retries += 1
            if retries > max_retries:
                raise
            progress_output(
                f"    Transient error (retry {retries}/{max_retries} in {delay:.0f}s): {e}"
            )
            time_module.sleep(delay)
            delay *= 2
            continue
        if status is None:
            continue

        now = clock()
        uploaded_bytes = status.resumable_progress
        total_upload_size = status.total_size
        if uploaded_bytes >= last_uploaded_bytes and now > last_sample_time:
            last_speed_bytes_per_second = (uploaded_bytes - last_uploaded_bytes) / (
                now - last_sample_time
            )
        last_uploaded_bytes = max(last_uploaded_bytes, uploaded_bytes)
        last_sample_time = now

        percent = min(100, max(0, int(status.progress() * 100)))
        if percent != last_percent:
            progress_output(
                format_progress_message(
                    progress_label,
                    percent,
                    show_speed,
                    last_speed_bytes_per_second,
                )
            )
            last_percent = percent

    if last_percent < 100:
        if total_upload_size is not None and total_upload_size >= last_uploaded_bytes:
            now = clock()
            if now > last_sample_time:
                last_speed_bytes_per_second = (
                    total_upload_size - last_uploaded_bytes
                ) / (now - last_sample_time)
        progress_output(
            format_progress_message(
                progress_label,
                100,
                show_speed,
                last_speed_bytes_per_second,
            )
        )

    return response


def format_progress_message(
    progress_label: str,
    percent: int,
    show_speed: bool = False,
    speed_bytes_per_second: float | None = None,
) -> str:
    """Format a progress line with an optional transfer speed suffix."""
    suffix = (
        f" (speed: {format_transfer_rate(speed_bytes_per_second)})"
        if show_speed
        else ""
    )
    return f"{progress_label}: {percent}%{suffix}"


def format_transfer_rate(bytes_per_second: float | None) -> str:
    """Format an upload speed value for CLI progress output."""
    if bytes_per_second is None or bytes_per_second <= 0:
        return "calculating"
    return f"{format_file_size(int(bytes_per_second))}/s"


def format_file_size(size_bytes: int) -> str:
    """Format a byte count for CLI output."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            if size >= 100 or size.is_integer():
                return f"{size:.0f} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.0f} GB"


def get_google_client(
    service: str,
    version: str,
    token_path: Path,
    scopes: list[str],
    client_secret: Path = Path("client_secret.json"),
) -> Any:
    """Authenticates and returns a Google API client using OAuth2 with token caching."""
    creds: Credentials | None = None
    if token_path.exists():
        with token_path.open("rb") as f:
            creds = pickle.load(f)
        # Force re-auth if cached token is missing any required scope
        if creds and creds.scopes and not set(scopes).issubset(creds.scopes):
            pr.amber(
                f"Token {token_path.name} missing required scopes — re-authenticating"
            )
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                pr.amber(
                    f"Token {token_path.name} expired or revoked — re-authenticating"
                )
                creds = None
        if not creds or not creds.valid:
            if not client_secret.exists():
                pr.no(f"Missing {client_secret}. Follow output/UPLOAD_SETUP.md")
                raise SystemExit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
            creds = flow.run_local_server(port=0)  # type: ignore[assignment]
        with token_path.open("wb") as f:
            pickle.dump(creds, f)
    return build(service, version, credentials=creds)


def check_api_probe(youtube: Any) -> tuple[bool, str]:
    """Probe the API with a 1-unit call to detect quota exhaustion."""
    _quota_reasons: frozenset[str] = frozenset({"quotaExceeded", "dailyLimitExceeded"})
    try:
        youtube.channels().list(part="id", mine=True).execute()
        return True, "API accessible — uploads should work"
    except HttpError as e:
        try:
            content = json.loads(e.content)
            reasons = {
                err.get("reason", "")
                for err in content.get("error", {}).get("errors", [])
            }
        except Exception:
            reasons = set()
        if reasons & _quota_reasons:
            return False, "Daily quota exceeded — uploads are blocked today"
        return False, f"API error ({e.status_code}) — check credentials or permissions"
    except Exception as e:
        return False, f"Connection error: {e}"


def check_token_local(token_path: Path) -> tuple[bool, str]:
    """Check OAuth token validity from disk with no API call."""
    if not token_path.exists():
        return False, f"Token file missing: {token_path.name}"
    try:
        with token_path.open("rb") as f:
            creds: Credentials = pickle.load(f)
        if creds.valid:
            expiry = (
                creds.expiry.strftime("%Y-%m-%d %H:%M UTC")
                if creds.expiry
                else "unknown"
            )
            return True, f"Token valid (expires {expiry})"
        if creds.expired and creds.refresh_token:
            return (
                True,
                "Token expired but has refresh token — will auto-refresh on real run",
            )
        return False, "Token invalid or missing refresh token — re-auth required"
    except Exception as e:
        return False, f"Could not read token: {e}"


def gdrive_folder_env_key(lang: str) -> str:
    """Returns the environment variable key for the Google Drive folder ID by language."""
    return f"GDRIVE_FOLDER_ID_{lang.upper()}"


def find_latest_review(
    pattern: str = "russian_review*.md", reviews_dir: Path = Path("reviews")
) -> Path | None:
    files = sorted(reviews_dir.glob(pattern))
    return files[-1] if files else None


def split_selected_playlists(raw: str) -> list[str]:
    """Split comma/semicolon review playlist selections into trimmed titles."""
    return [part.strip() for part in re.split(r"[,;]", raw) if part.strip()]


def list_channel_playlists(youtube: Any) -> dict[str, str]:
    """Return existing channel playlists keyed by exact trimmed playlist title."""
    playlists: dict[str, str] = {}
    page_token: str | None = None
    while True:
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50,
            pageToken=page_token,
        )
        response = request.execute()
        for item in response.get("items", []):
            title = item.get("snippet", {}).get("title", "").strip()
            playlist_id = item.get("id", "")
            if title and playlist_id:
                playlists[title] = playlist_id
        page_token = response.get("nextPageToken")
        if not page_token:
            return playlists


def parse_review(review_path: Path) -> dict[str, dict[str, Any]]:
    content = review_path.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)
    result: dict[str, dict[str, Any]] = {}
    for section in sections:
        source_m = re.search(r"## Source: (.*)", section)
        date_m = re.search(r"\*\*Recording Date:\*\*\s*(.*)", section)
        publish_m = re.search(r"\*\*Publish Date:\*\*\s*(.*)", section)
        approved_m = re.search(r"\*\*Approved:\*\*\s*(yes|no)", section, re.IGNORECASE)
        title_m = re.search(r"\*\*Suggested Title:\*\*\s*(.*)", section)
        playlist_overview_m = re.search(
            r"\*\*Channel Playlist Overview:\*\*\s*(.*)", section
        )
        selected_playlist_m = re.search(
            r"^\*\*Selected Playlist:\*\*[^\S\r\n]*(.*)$", section, re.MULTILINE
        )
        desc_m = re.search(
            r"\*\*Suggested Description:\*\*\s*(.*?)(?=\n\*\*Suggested Tags:|\Z)",
            section,
            re.DOTALL,
        )
        tags_m = re.search(r"\*\*Suggested Tags:\*\*\s*(.*)", section)
        chapters_m = re.search(
            r"\*\*Chapters:\*\*\n((?:\[[\d:.]+\][^\n]+\n?)+)", section
        )

        approved = approved_m.group(1).lower() == "yes" if approved_m else False

        if source_m and title_m and desc_m:
            stem = unicodedata.normalize("NFC", Path(source_m.group(1).strip()).stem)
            result[stem] = {
                "approved": approved,
                "title": title_m.group(1).strip(),
                "recording_date": date_m.group(1).strip() if date_m else "",
                "publish_date": publish_m.group(1).strip() if publish_m else "",
                "channel_playlist_overview": playlist_overview_m.group(1).strip()
                if playlist_overview_m
                else "",
                "selected_playlists": split_selected_playlists(
                    selected_playlist_m.group(1) if selected_playlist_m else ""
                ),
                "description": desc_m.group(1).strip(),
                "tags": tags_m.group(1).strip() if tags_m else "",
                "chapters": chapters_m.group(1).strip() if chapters_m else "",
            }
    return result


def _extract_core_urls(text: str) -> list[str]:
    """Extract normalized URLs for deduplication."""
    urls = []
    for word in text.split():
        # strip punctuation
        word = word.strip("()[]{},;:\"'")
        if ("." in word and "/" in word) or word.startswith("http"):
            # normalize by stripping http://, https://, www., and trailing punctuation
            word = re.sub(r"^https?://", "", word)
            word = re.sub(r"^www\.", "", word)
            word = word.rstrip("/.,!?;:")
            if word:
                urls.append(word)
    return urls


def build_description(
    recording_date: str,
    description: str,
    tags: str = "",
    chapters: str = "",
    bio_link: str | None = None,
) -> str:
    date_and_desc = (
        f"{recording_date}\n{description}" if recording_date else description
    )
    parts: list[str] = [date_and_desc]
    if bio_link and bio_link not in description:
        # Avoid duplication if any core URL in the bio link is already present
        urls_in_bio = _extract_core_urls(bio_link)
        if not urls_in_bio or not any(u in description for u in urls_in_bio):
            parts.append(bio_link)
    if chapters:
        parsed = parse_chapters_str(chapters)
        if parsed:
            parts.append(chapters_to_youtube(parsed))
    if tags:
        parts.append(tags)
    return "\n\n".join(parts)


def parse_tags_for_api(tags_str: str) -> list[str]:
    return [t.lstrip("#") for t in tags_str.split() if t.startswith("#")]


def hms_to_minutes(hms: str) -> float:
    """Convert M:SS, MM:SS, or H:MM:SS to decimal minutes."""
    parts = hms.split(":")
    if len(parts) == 3:  # H:MM:SS
        return int(parts[0]) * 60.0 + int(parts[1]) + int(parts[2]) / 60.0
    elif len(parts) == 2:  # MM:SS
        return int(parts[0]) + int(parts[1]) / 60.0
    return float(hms)  # Fallback to decimal minutes


def parse_chapters_str(raw: str) -> list[tuple[float, str]]:
    """Parse a multiline '[X.X]' or '[MM:SS]' block from the review file."""
    result: list[tuple[float, str]] = []
    for line in raw.strip().splitlines():
        m = re.match(r"\[([\d.:]+)\]\s+(.+)", line.strip())
        if m:
            ts_str = m.group(1)
            name = m.group(2).strip()
            if ":" in ts_str:
                ts = hms_to_minutes(ts_str)
            else:
                ts = float(ts_str)
            result.append((ts, name))
    return result


def minutes_to_hms(mins: float) -> str:
    """Convert decimal minutes to M:SS or H:MM:SS format."""
    total_s = round(mins * 60)
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def chapters_to_youtube(chapters: list[tuple[float, str]]) -> str:
    """Convert [(float_minutes, name), ...] to YouTube chapter format (M:SS or H:MM:SS)."""
    lines: list[str] = []
    for mins, name in chapters:
        ts = minutes_to_hms(mins)
        lines.append(f"{ts} {name}")
    return "\n".join(lines)


def find_audio_for_mp4(
    mp4_path: Path, audio_dir: Path = Path("output/audio")
) -> Path | None:
    mp3 = find_path_by_normalized_name(audio_dir, f"{mp4_path.stem}.mp3")
    return mp3 if mp3.exists() else None


def load_history(history_path: Path) -> dict[str, dict[str, str]]:
    if history_path.exists():
        try:
            return json.loads(history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pr.amber(f"History file {history_path} is corrupt, starting fresh.")
            return {}
    return {}


def normalize_text(value: str) -> str:
    """Return NFC text for reliable macOS-safe Unicode comparisons."""
    return unicodedata.normalize("NFC", value)


def normalize_history_name(name: str) -> str:
    """Normalize a history key or filename by final filename."""
    return normalize_text(Path(name).name)


def normalize_history_key(key: str) -> str:
    """Normalize a full history key while preserving slash-separated folders."""
    return "/".join(normalize_text(part) for part in key.split("/"))


def find_path_by_normalized_name(directory: Path, filename: str) -> Path:
    """Return the existing child whose name matches filename after NFC normalization."""
    candidate = directory / filename
    if candidate.exists():
        return candidate

    target = normalize_history_name(filename)
    if not directory.exists():
        return candidate

    for child in directory.iterdir():
        if normalize_history_name(child.name) == target:
            return child
    return candidate


def get_uploaded_history_entry(
    history: dict[str, dict[str, Any]], final_name: str
) -> dict[str, Any] | None:
    """Return uploaded history entry matching an exact final media filename."""
    target = normalize_history_name(final_name)
    for key, entry in history.items():
        if normalize_history_name(key) == target and entry.get("status") == "uploaded":
            return entry
    return None


def is_uploaded_in_history(history: dict[str, dict[str, Any]], final_name: str) -> bool:
    """True when history has an uploaded entry for the exact final media filename."""
    return get_uploaded_history_entry(history, final_name) is not None


def is_stem_uploaded_in_history(history: dict[str, dict[str, Any]], stem: str) -> bool:
    """True when any uploaded history key starts with stem (handles speaker-name suffix).

    Covers the case where the transcript stem ("2021-11-06 - Title") has not been
    renamed yet on this machine but the history key includes an appended speaker name
    ("2021-11-06 - Title - Bhikkhu Devamitta.mp4").
    """
    target = normalize_text(stem).lower()
    for key, entry in history.items():
        if entry.get("status") != "uploaded":
            continue
        key_stem = normalize_text(Path(key).stem).lower()
        if key_stem == target or key_stem.startswith(target + " -"):
            return True
    return False


def get_uploaded_history_key_entry(
    history: dict[str, dict[str, Any]], key: str
) -> dict[str, Any] | None:
    """Return uploaded history entry matching a full normalized history key."""
    target = normalize_history_key(key)
    for existing_key, entry in history.items():
        if (
            normalize_history_key(existing_key) == target
            and entry.get("status") == "uploaded"
        ):
            return entry
    return None


def is_uploaded_key_in_history(history: dict[str, dict[str, Any]], key: str) -> bool:
    """True when history has an uploaded entry for the full normalized key."""
    return get_uploaded_history_key_entry(history, key) is not None


def load_nested_history(
    history_path: Path,
    language: str,
    section: str | None = None,
    legacy_path: Path | None = None,
    _migrated: bool = False,
) -> dict[str, dict[str, str]]:
    full_history: dict = {}
    if history_path.exists():
        try:
            data = json.loads(history_path.read_text(encoding="utf-8"))
            if data and isinstance(data, dict):
                # Treat as nested if ANY key looks like a language code (2 lowercase letters).
                # Checking only 'language in data' fails when the file already has {"en": {...}}
                # and we load with language="ru" — it would re-wrap the whole file.
                _known_lang_codes: frozenset[str] = frozenset({"ru", "en"})
                is_nested = any(k in _known_lang_codes for k in data)
                if not is_nested:
                    full_history = {language: data}
                    history_path.write_text(
                        json.dumps(full_history, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    pr.green(
                        f"Migrated flat history to nested format in {history_path.name}"
                    )
                    _migrated = True
                else:
                    full_history = data
        except json.JSONDecodeError:
            pr.amber(f"History file {history_path} is corrupt, starting fresh.")
            full_history = {}

    needs_migration = False
    if legacy_path and legacy_path.exists():
        lang_section = full_history.get(language, {})
        if section and section not in lang_section:
            needs_migration = True
        elif not section and not lang_section:
            needs_migration = True

    if needs_migration:
        assert legacy_path is not None
        try:
            legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
            if isinstance(legacy_data, dict) and legacy_data:
                if section:
                    if language not in full_history:
                        full_history[language] = {}
                    full_history[language][section] = legacy_data
                else:
                    full_history[language] = legacy_data
                pr.green(f"Migrated legacy history from {legacy_path.name}")
                _migrated = True
        except json.JSONDecodeError:
            pr.amber(f"Legacy history file {legacy_path} is corrupt.")

    if _migrated:
        history_path.write_text(
            json.dumps(full_history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if language not in full_history:
        full_history[language] = {}

    if section:
        if section not in full_history[language]:
            full_history[language][section] = {}
        return full_history[language][section]

    return full_history[language]


def save_nested_history(
    history_path: Path,
    language: str,
    section_data: dict[str, dict[str, str]],
    section: str | None = None,
) -> None:
    full_history: dict = {}
    if history_path.exists():
        try:
            full_history = json.loads(history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pr.amber(f"History file {history_path} is corrupt, overwriting.")
            full_history = {}

    if language not in full_history:
        full_history[language] = {}

    if section:
        full_history[language][section] = section_data
    else:
        full_history[language] = section_data

    history_path.write_text(
        json.dumps(full_history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_history(history_path: Path, history: dict[str, dict[str, str]]) -> None:
    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def mark_uploaded(
    history: dict[str, dict[str, str]], key: str, platform_id: str
) -> None:
    normalized_key = normalize_history_key(key)
    for existing_key in list(history):
        if normalize_history_key(existing_key) == normalized_key:
            history.pop(existing_key)
    history[normalized_key] = {
        "platform_id": platform_id,
        "status": "uploaded",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


def confirm_and_save(
    history_path: Path,
    history: dict[str, dict[str, str]],
    key: str,
    platform_id: str,
    platform_name: str,
) -> None:
    mark_uploaded(history, key, platform_id)
    save_history(history_path, history)
    pr.yes(f"Uploaded to {platform_name}: {key} (ID: {platform_id})")


def confirm_and_save_nested(
    history_path: Path,
    language: str,
    history: dict[str, dict[str, str]],
    key: str,
    platform_id: str,
    platform_name: str,
    section: str | None = None,
) -> None:
    mark_uploaded(history, key, platform_id)
    save_nested_history(history_path, language, history, section)
    pr.yes(f"Uploaded to {platform_name}: {key} (ID: {platform_id})")


def find_mp4s_with_album(input_dir: Path) -> list[tuple[Path, str | None]]:
    """Walk input_dir one level deep; return (mp4_path, album_or_None)."""
    results: list[tuple[Path, str | None]] = []
    if not input_dir.exists():
        return results
    for item in sorted(input_dir.iterdir()):
        if item.is_file() and item.suffix.lower() == ".mp4":
            results.append((item, None))
        elif item.is_dir():
            for mp4 in sorted(item.glob("*.mp4")):
                results.append((mp4, item.name))
    return results


def make_history_key(mp4_path: Path, album: str | None) -> str:
    raw_key = f"{album}/{mp4_path.name}" if album else mp4_path.name
    return normalize_history_key(raw_key)


def match_mp4_to_review(
    mp4_path: Path,
    review: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    stem = unicodedata.normalize("NFC", mp4_path.stem)
    return review.get(stem)
