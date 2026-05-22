"""Compares youtube_history.json against actual YouTube channel videos and reports mismatches."""

import argparse
from pathlib import Path

from tools.printer import printer as pr
from tools.uploader_common import (
    get_google_client,
    load_nested_history,
    save_nested_history,
)

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


def get_channel_videos(youtube) -> dict[str, str]:
    """Returns {video_id: title} for every video on the authenticated channel."""
    ch_resp = youtube.channels().list(mine=True, part="contentDetails").execute()
    if not ch_resp.get("items"):
        return {}
    uploads_id = ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos: dict[str, str] = {}
    next_page: str | None = None
    while True:
        resp = (
            youtube.playlistItems()
            .list(
                playlistId=uploads_id,
                part="snippet",
                maxResults=50,
                pageToken=next_page,
            )
            .execute()
        )
        for item in resp.get("items", []):
            vid_id = item["snippet"]["resourceId"]["videoId"]
            title = item["snippet"]["title"]
            videos[vid_id] = title
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
    return videos


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare youtube_history.json with actual YouTube channel videos."
    )
    parser.add_argument("--lang", choices=["ru", "en"], default="en")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove history entries whose video no longer exists on YouTube",
    )
    args = parser.parse_args()

    token_path = TOKEN_PATHS[args.lang]
    youtube = get_google_client("youtube", "v3", token_path, SCOPES, CLIENT_SECRET)

    pr.green("Fetching videos from YouTube channel...")
    pr.bip()
    yt_videos = get_channel_videos(youtube)
    pr.yes(f"Found {len(yt_videos)} videos on YouTube")

    lang_history = load_nested_history(HISTORY_PATH, args.lang)

    history_by_id: dict[str, str] = {}
    for key, entry in lang_history.items():
        pid = entry.get("platform_id", "")
        if pid:
            history_by_id[pid] = key

    yt_ids = set(yt_videos.keys())
    history_ids = set(history_by_id.keys())

    matched = history_ids & yt_ids
    orphaned = history_ids - yt_ids
    untracked = yt_ids - history_ids

    pr.green_title(f"History vs YouTube ({args.lang})")
    pr.white(f"  Matched (in both):       {len(matched)}")

    if untracked:
        pr.amber(f"  On YouTube, not in history ({len(untracked)}):")
        for vid_id in sorted(untracked):
            pr.white(f"    {vid_id}  {yt_videos[vid_id]!r}")

    if orphaned:
        pr.amber(f"  In history, not on YouTube ({len(orphaned)}):")
        for vid_id in sorted(orphaned):
            key = history_by_id[vid_id]
            entry = lang_history.get(key, {})
            pr.white(f"    {vid_id}  {key!r}")
            pr.white(f"           uploaded_at={entry.get('uploaded_at', '?')}")

        if args.clean:
            pr.green("Removing orphaned entries...")
            for vid_id in orphaned:
                key = history_by_id[vid_id]
                del lang_history[key]
                pr.yes(f"  Removed: {key}")
            save_nested_history(HISTORY_PATH, args.lang, lang_history)
            pr.yes(f"History updated — {len(orphaned)} entries removed")
        else:
            pr.amber("Run with --clean to remove these from history")

    if not orphaned and not untracked:
        pr.yes("History is in sync with YouTube")


if __name__ == "__main__":
    main()
