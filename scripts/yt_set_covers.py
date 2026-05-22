"""Retroactively sets YouTube thumbnails for already-uploaded videos using stored history."""

import argparse
import json
import time
import unicodedata
from pathlib import Path
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from tools.printer import printer as pr
from tools.uploader_common import check_api_probe, get_google_client

CLIENT_SECRET = Path("client_secret.json")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
HISTORY_PATH = Path("output/youtube_history.json")

TOKEN_PATHS: dict[str, Path] = {
    "ru": Path("youtube_token_ru.json"),
    "en": Path("youtube_token_en.json"),
}

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


UPLOAD_DELAY_SEC = 3
RETRY_WAITS = [30, 60, 120]  # seconds to wait on each successive 429
QUOTA_EXCEEDED_REASONS = {"quotaExceeded", "dailyLimitExceeded"}


class QuotaExceededError(Exception):
    pass


def _get_error_reasons(e: HttpError) -> set[str]:
    try:
        content = json.loads(e.content)
        return {
            err.get("reason", "") for err in content.get("error", {}).get("errors", [])
        }
    except Exception:
        return set()


def set_thumbnail_with_retry(youtube: Any, video_id: str, cover_path: Path) -> None:
    """Upload a thumbnail, retrying on transient 429s but stopping on daily quota exceeded."""
    for attempt, wait in enumerate([0, *RETRY_WAITS]):
        if wait:
            pr.amber(
                f"    Rate-limited — waiting {wait}s before retry {attempt}/{len(RETRY_WAITS)}..."
            )
            time.sleep(wait)
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    str(cover_path), mimetype="image/jpeg", resumable=True
                ),
            ).execute()
            return
        except HttpError as e:
            if _get_error_reasons(e) & QUOTA_EXCEEDED_REASONS:
                raise QuotaExceededError(f"Daily quota exceeded: {e}") from e
            if e.status_code == 429 and attempt < len(RETRY_WAITS):
                continue
            raise


def fetch_videos_with_custom_thumbnail(youtube: Any, video_ids: list[str]) -> set[str]:
    """Return video IDs that already have a custom thumbnail (maxres key present)."""
    has_thumb: set[str] = set()
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        resp = (
            youtube.videos()
            .list(
                part="snippet",
                id=",".join(chunk),
            )
            .execute()
        )
        for item in resp.get("items", []):
            thumbs = item.get("snippet", {}).get("thumbnails", {})
            if "maxres" in thumbs:
                has_thumb.add(item["id"])
    return has_thumb


def load_history() -> dict[str, dict[str, dict[str, str]]]:
    if not HISTORY_PATH.exists():
        return {}
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set YouTube thumbnails retroactively for uploaded videos."
    )
    parser.add_argument("--lang", choices=["ru", "en"], default="en")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N videos")
    parser.add_argument("--dry-run", action="store_true", help="Do not call the API")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip YouTube API check — trust thumbnail_set flag in history",
    )
    args = parser.parse_args()

    folder_name = LANG_TO_FOLDER[args.lang]
    covers_dir = Path(f"output/covers/{folder_name}")
    token_path = TOKEN_PATHS[args.lang]

    history = load_history()
    lang_history: dict[str, dict[str, str]] = history.get(args.lang, {})

    if not lang_history:
        pr.no(f"No upload history for lang={args.lang} in {HISTORY_PATH}")
        return

    candidates: list[tuple[str, str, Path, str]] = []
    for key, entry in lang_history.items():
        video_id = entry.get("platform_id", "")
        if not video_id or entry.get("status") != "uploaded":
            continue
        stem = unicodedata.normalize("NFC", Path(key).stem)
        cover_path = covers_dir / f"{stem}.jpg"
        if cover_path.exists():
            candidates.append((video_id, stem, cover_path, key))

    pr.green_title(
        f"Found {len(candidates)} uploaded videos with matching covers ({folder_name})"
    )

    if not candidates:
        pr.amber("Nothing to do — generate covers first with yt_cover_gen.py")
        return

    if args.limit > 0:
        candidates = candidates[: args.limit]

    already_done = [
        c for c in candidates if lang_history.get(c[3], {}).get("thumbnail_set")
    ]
    candidates = [
        c for c in candidates if not lang_history.get(c[3], {}).get("thumbnail_set")
    ]
    if already_done:
        pr.amber(f"  Skipping {len(already_done)} already set in history")

    if not candidates:
        pr.yes("All covers already set in history — nothing to do")
        return

    if args.dry_run:
        for video_id, stem, cover_path, _key in candidates:
            pr.white(f"  [DRY RUN] {stem} → videoId={video_id}")
        pr.green("Probing YouTube API for quota status...")
        pr.bip()
        yt_probe = get_google_client("youtube", "v3", token_path, SCOPES, CLIENT_SECRET)
        ok, msg = check_api_probe(yt_probe)
        if ok:
            pr.yes(msg)
        else:
            pr.no(msg)
        return

    youtube = get_google_client("youtube", "v3", token_path, SCOPES, CLIENT_SECRET)

    if not args.force:
        pr.green("Checking which videos already have a custom thumbnail...")
        all_ids = [vid_id for vid_id, _, _, _ in candidates]
        already_set = fetch_videos_with_custom_thumbnail(youtube, all_ids)
        if already_set:
            pr.amber(f"  Skipping {len(already_set)} already have a custom thumbnail")
        candidates = [c for c in candidates if c[0] not in already_set]
        if not candidates:
            pr.yes("All videos already have custom thumbnails — nothing to do")
            return

    set_count = 0
    error_count = 0
    for video_id, stem, cover_path, key in candidates:
        pr.green(f"  Setting thumbnail: {stem}")
        pr.bip()
        try:
            set_thumbnail_with_retry(youtube, video_id, cover_path)
            pr.yes(f"  Set: {cover_path.name}")
            lang_history[key]["thumbnail_set"] = True  # type: ignore[assignment]
            HISTORY_PATH.write_text(
                json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            set_count += 1
        except QuotaExceededError as e:
            pr.no(
                f"Daily thumbnail quota exceeded after {set_count} uploads — stopping"
            )
            pr.amber(str(e))
            pr.green("Re-run with --force to continue from where this left off.")
            break
        except Exception as e:
            pr.no(f"  Failed: {stem}")
            pr.amber(str(e))
            error_count += 1
        time.sleep(UPLOAD_DELAY_SEC)

    pr.yes(f"Done: {set_count} set, {error_count} errors")


if __name__ == "__main__":
    main()
