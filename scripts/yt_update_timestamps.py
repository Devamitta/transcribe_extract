"""Add YouTube chapter timestamps to uploaded video descriptions that are missing them.

Usage:
    uv run python scripts/yt_update_timestamps.py --lang ru
    uv run python scripts/yt_update_timestamps.py --lang en
    uv run python scripts/yt_update_timestamps.py --lang ru --dry-run
    uv run python scripts/yt_update_timestamps.py --lang ru --force       # overwrite existing chapters
    uv run python scripts/yt_update_timestamps.py --lang ru --limit 3     # process first 3 only
"""

import argparse
import pickle
import re
import unicodedata
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from tools.printer import printer as pr
from tools.uploader_common import (
    build_description,
    find_latest_review,
    load_nested_history,
    parse_review,
)


HISTORY_PATH = Path("output/youtube_history.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_PATHS: dict[str, Path] = {
    "ru": Path("youtube_token_ru_edit.json"),
    "en": Path("youtube_token_en_edit.json"),
}
CLIENT_SECRET = Path("client_secret.json")
LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


def get_youtube_client(token_path: Path):
    """Authenticates and returns a YouTube API client with edit scopes."""
    creds: Credentials | None = None
    if token_path.exists():
        with token_path.open("rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                pr.no(f"Missing {CLIENT_SECRET}. Follow output/UPLOAD_SETUP.md")
                raise SystemExit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)  # type: ignore[assignment]
        with token_path.open("wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)


def fetch_channel_videos(youtube) -> dict[str, str]:
    """Returns {video_id: title} for every video in the authenticated channel's uploads playlist."""
    ch_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_id = ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    titles: dict[str, str] = {}
    page_token: str | None = None
    while True:
        pl_resp = (
            youtube.playlistItems()
            .list(
                part="snippet",
                playlistId=uploads_id,
                maxResults=50,
                pageToken=page_token,
            )
            .execute()
        )
        for item in pl_resp.get("items", []):
            vid_id: str = item["snippet"]["resourceId"]["videoId"]
            titles[vid_id] = item["snippet"]["title"]
        page_token = pl_resp.get("nextPageToken")
        if not page_token:
            break
    return titles


def description_has_chapters(description: str) -> bool:
    """Returns True if any line in description starts with "0:" or "00:" (YouTube chapter format)."""
    for line in description.splitlines():
        if re.match(r"^00?:\d{2}", line.strip()):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Add YouTube chapter timestamps to uploaded video descriptions."
    )
    parser.add_argument(
        "--lang",
        type=str,
        required=True,
        choices=["ru", "en"],
        help="Language (ru|en).",
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder name (e.g. 'russian'). Defaults based on lang.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not update, just list"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update even if description already has chapters",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Process only first N videos"
    )
    args = parser.parse_args()

    history = load_nested_history(HISTORY_PATH, args.lang)
    if not history:
        pr.no(f"No history found for language '{args.lang}'.")
        return

    folder_name = args.folder or LANG_TO_FOLDER[args.lang]
    review_path = find_latest_review(f"{folder_name}_review*.md")
    if not review_path or not review_path.exists():
        pr.no("Review file not found.")
        raise SystemExit(1)

    review = parse_review(review_path)
    if not review:
        pr.no(f"No approved talks found in '{review_path.name}'.")
        return

    to_update: list[tuple[str, str, dict]] = []  # (stem, video_id, meta)
    no_match: list[tuple[str, str, str]] = []  # (stem, video_id, reason)

    for key, v in history.items():
        if v.get("status") == "uploaded" and v.get("platform_id"):
            # Strip album/ and .mp4
            stem = unicodedata.normalize("NFC", Path(key).stem)
            video_id = v["platform_id"]
            if stem not in review:
                no_match.append((stem, video_id, "not in review"))
            else:
                meta = review[stem]
                if meta.get("chapters"):
                    to_update.append((stem, video_id, meta))
                else:
                    no_match.append((stem, video_id, "no chapters in review"))

    if not to_update and not no_match:
        pr.yes("No videos to process.")
        return

    youtube = get_youtube_client(TOKEN_PATHS[args.lang])

    if no_match:
        ids = [vid for _, vid, _ in no_match]
        title_map: dict[str, str] = {}
        for i in range(0, len(ids), 50):
            batch = ids[i : i + 50]
            resp = youtube.videos().list(part="snippet", id=",".join(batch)).execute()
            for item in resp.get("items", []):
                title_map[item["id"]] = item["snippet"]["title"]
        pr.amber(f"\n{len(no_match)} uploaded videos do not match criteria:")
        for stem, video_id, reason in no_match:
            title = title_map.get(video_id, stem)
            pr.amber(f"  [{reason}] {title}")

    if not to_update:
        return

    if args.limit > 0:
        to_update = to_update[: args.limit]
    updated, skipped, failed = 0, 0, 0
    has_chapters_titles: list[str] = []

    for stem, video_id, meta in to_update:
        try:
            resp = youtube.videos().list(part="snippet", id=video_id).execute()
            items = resp.get("items", [])
            if not items:
                pr.amber(f"  {video_id}: not found on YouTube — skipping")
                skipped += 1
                continue

            snippet = items[0]["snippet"]
            if not args.force and description_has_chapters(
                snippet.get("description", "")
            ):
                has_chapters_titles.append(snippet.get("title", stem))
                skipped += 1
                continue

            new_desc = build_description(
                meta["recording_date"],
                meta["description"],
                meta.get("tags", ""),
                meta["chapters"],
            )

            if args.dry_run:
                pr.white(f"\n  {video_id} ({stem})")
                pr.white("  --- description ---")
                for line in new_desc.splitlines():
                    pr.white(f"  {line}")
                pr.white("  --- end ---")
                continue

            snippet["description"] = new_desc
            youtube.videos().update(
                part="snippet",
                body={"id": video_id, "snippet": snippet},
            ).execute()
            pr.yes(f"  Updated {video_id} ({stem})")
            updated += 1
        except Exception as e:
            pr.no(f"  Failed {video_id} ({stem}): {e}")
            failed += 1

    if has_chapters_titles:
        pr.amber(
            f"\n{len(has_chapters_titles)} videos already have chapters on YouTube:"
        )
        for title in has_chapters_titles:
            pr.amber(f"  {title}")

    # Report channel videos not tracked in history at all
    known_ids = {vid for _, vid, _ in no_match} | {vid for _, vid, _ in to_update}
    channel_videos = fetch_channel_videos(youtube)
    untracked = {
        vid: title for vid, title in channel_videos.items() if vid not in known_ids
    }
    if untracked:
        pr.amber(f"\n{len(untracked)} channel videos not in history:")
        for title in untracked.values():
            pr.amber(f"  [not in history] {title}")

    if args.dry_run:
        return
    pr.yes(f"Done. {updated} updated, {skipped} skipped, {failed} failed.")


if __name__ == "__main__":
    main()
