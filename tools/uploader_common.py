"""Shared utilities for YouTube and Google Drive upload scripts."""

import json
import pickle
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tools.printer import printer as pr


def get_google_client(
    service: str,
    version: str,
    token_path: Path,
    scopes: list[str],
    client_secret: Path = Path("client_secret.json"),
):
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
            creds.refresh(Request())
        else:
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


def parse_review(review_path: Path) -> dict[str, dict[str, str]]:
    content = review_path.read_text(encoding="utf-8")
    sections = re.split(r"\n---", content)
    result: dict[str, dict[str, str]] = {}
    for section in sections:
        source_m = re.search(r"## Source: (.*)", section)
        date_m = re.search(r"\*\*Recording Date:\*\*\s*(.*)", section)
        approved_m = re.search(r"\*\*Approved:\*\*\s*(yes|no)", section, re.IGNORECASE)
        title_m = re.search(r"\*\*Suggested Title:\*\*\s*(.*)", section)
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

        if source_m and title_m and desc_m and approved:
            stem = unicodedata.normalize("NFC", Path(source_m.group(1).strip()).stem)
            result[stem] = {
                "title": title_m.group(1).strip(),
                "recording_date": date_m.group(1).strip() if date_m else "",
                "description": desc_m.group(1).strip(),
                "tags": tags_m.group(1).strip() if tags_m else "",
                "chapters": chapters_m.group(1).strip() if chapters_m else "",
            }
    return result


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
        parts.append(bio_link)
    if tags:
        parts.append(tags)
    if chapters:
        parsed = parse_chapters_str(chapters)
        if parsed:
            parts.append(chapters_to_youtube(parsed))
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
    total_s = int(round(mins * 60))
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
    mp3 = audio_dir / f"{mp4_path.stem}.mp3"
    return mp3 if mp3.exists() else None


def load_history(history_path: Path) -> dict[str, dict[str, str]]:
    if history_path.exists():
        try:
            return json.loads(history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pr.amber(f"History file {history_path} is corrupt, starting fresh.")
            return {}
    return {}


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
    history[key] = {
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
    return f"{album}/{mp4_path.name}" if album else mp4_path.name


def match_mp4_to_review(
    mp4_path: Path,
    review: dict[str, dict[str, str]],
) -> dict[str, str] | None:
    stem = unicodedata.normalize("NFC", mp4_path.stem)
    return review.get(stem)
