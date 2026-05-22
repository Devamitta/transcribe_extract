"""Batch-uploads Dhamma MP4s to YouTube with playlist and history support."""

import argparse
import pickle
import unicodedata
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from tools.printer import printer as pr
from tools.uploader_common import (
    BIO_LINKS,
    build_description,
    confirm_and_save_nested,
    find_mp4s_with_album,
    load_nested_history,
    make_history_key,
    match_mp4_to_review,
    parse_review,
    parse_tags_for_api,
)


CLIENT_SECRET = Path("client_secret.json")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
]
HISTORY_PATH = Path("output/youtube_history.json")
DEFAULT_BATCH = 6

TOKEN_PATHS: dict[str, Path] = {
    "ru": Path("youtube_token_ru.json"),
    "en": Path("youtube_token_en.json"),
}

LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


def get_google_client(service: str, version: str, token_path: Path):
    """Authenticates and returns a Google API client."""
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
    return build(service, version, credentials=creds)


def find_existing_playlist(youtube, title: str) -> str | None:
    """Finds an existing YouTube playlist by title. Returns ID or None."""
    response = (
        youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
    )
    for item in response.get("items", []):
        if item["snippet"]["title"] == title:
            return item["id"]
    return None


def parse_recording_date(date_str: str) -> str | None:
    """Convert DD-MM-YYYY to RFC 3339 for YouTube recordingDate field."""
    try:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime(
            "%Y-%m-%dT00:00:00.000Z"
        )
    except ValueError:
        return None


def upload_video(
    youtube,
    mp4_path: Path,
    title: str,
    description: str,
    tags: list[str],
    lang: str,
    recording_date: str = "",
) -> str:
    """Uploads a single video to YouTube."""
    media = MediaFileUpload(str(mp4_path), mimetype="video/mp4", resumable=True)
    body: dict = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "27",  # Education
            "tags": tags,
            "defaultLanguage": lang,
            "defaultAudioLanguage": lang,
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    parts = "snippet,status"
    iso_date = parse_recording_date(recording_date) if recording_date else None
    if iso_date:
        body["recordingDetails"] = {"recordingDate": iso_date}
        parts = "snippet,status,recordingDetails"

    response = (
        youtube.videos().insert(part=parts, body=body, media_body=media).execute()
    )
    return response["id"]


def main():
    parser = argparse.ArgumentParser(
        description="Batch-uploads Dhamma MP4s to YouTube with playlist and history support."
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="en",
        choices=["ru", "en"],
        help="Language of the talk (ru|en).",
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder name (e.g. 'russian'). Defaults to lang-based folder (ru→russian, en→english).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not upload, just list"
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH, help="Max uploads"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N MP4s by date (0=unlimited)",
    )
    parser.add_argument("--review-file", type=Path, help="Manual review file path")
    parser.add_argument("--input-dir", type=Path, help="Override MP4 directory")
    parser.add_argument(
        "--files-from-log",
        type=Path,
        help="Only upload files listed in this log (one path per line).",
    )
    args = parser.parse_args()

    if args.folder is not None:
        folder_names = [args.folder]
    else:
        folder_names = [LANG_TO_FOLDER[args.lang]]

    if not folder_names:
        pr.no("No subfolders found in 'output/transcribed/'.")
        return

    token_path = TOKEN_PATHS[args.lang]
    history = load_nested_history(HISTORY_PATH, args.lang)

    # Gather all pending uploads from selected folders
    all_to_upload: list[tuple[Path, str | None, dict]] = []
    lang_folder = LANG_TO_FOLDER.get(args.lang or "en", "english")
    for folder_name in folder_names:
        review_path = args.review_file or Path("reviews") / f"{lang_folder}_review.md"
        if not review_path or not review_path.exists():
            continue

        review = parse_review(review_path)
        input_dir = args.input_dir or Path("output/video") / folder_name

        if not input_dir.exists():
            continue

        mp4s = find_mp4s_with_album(input_dir)
        for path, album in mp4s:
            key = make_history_key(path, album)
            if key in history and history[key].get("status") == "uploaded":
                continue

            meta = match_mp4_to_review(path, review)
            if meta:
                all_to_upload.append((path, album, meta))
            else:
                # Only warn if folder was explicitly specified
                if args.folder:
                    pr.amber(
                        f"    Missing metadata for {path.name} in folder '{folder_name}'"
                    )

    if not all_to_upload:
        pr.green("Everything already uploaded.")
        return

    # Restrict to specific files if a created-log was provided
    if args.files_from_log and args.files_from_log.exists():
        log_content = args.files_from_log.read_text(encoding="utf-8")
        specific: set[Path] = {
            Path(line.strip()) for line in log_content.splitlines() if line.strip()
        }
        if specific:
            all_to_upload = [t for t in all_to_upload if t[0] in specific]

    if not all_to_upload:
        pr.green("No new uploads for this run.")
        return

    # Sort all pending uploads chronologically by recording date
    def _parse_date(t: tuple[Path, str | None, dict]) -> datetime:
        try:
            return datetime.strptime(t[2]["recording_date"], "%d-%m-%Y")
        except (ValueError, KeyError):
            return datetime.min

    all_to_upload.sort(key=_parse_date)

    if args.limit > 0:
        to_upload = all_to_upload[: args.limit]
    elif args.batch_size > 0:
        to_upload = all_to_upload[: args.batch_size]
    else:
        to_upload = all_to_upload

    pr.green(f"{len(to_upload)} video(s) queued for YouTube upload.")

    if args.dry_run:
        pr.green_title(
            f"[DRY-RUN] Found {len(to_upload)} videos to upload (Token: {token_path.name}):"
        )
        for path, album, meta in to_upload:
            tags_str = meta.get("tags", "")
            desc = build_description(
                meta["recording_date"],
                meta["description"],
                tags_str,
                chapters=meta.get("chapters", ""),
                bio_link=BIO_LINKS.get(args.lang),
            )
            api_tags = parse_tags_for_api(tags_str)
            iso_date = parse_recording_date(meta["recording_date"])
            pr.white(f"\n  File:           {path}")
            pr.white(f"  Playlist:       {album or '(none)'}")
            pr.white(f"  Title:          {meta['title']}")
            pr.white(f"  Language:       {args.lang}")
            pr.white(
                f"  Recording date: {meta['recording_date']} → {iso_date or 'INVALID DATE'}"
            )
            pr.white(f"  Tags:           {', '.join(api_tags)}")
            pr.white(f"  Description:\n{desc}")
        return

    youtube = get_google_client("youtube", "v3", token_path)
    playlist_cache: dict[str, str] = {}

    for path, album, meta in to_upload:
        tags_str = meta.get("tags", "")
        desc = build_description(
            meta["recording_date"],
            meta["description"],
            tags_str,
            chapters=meta.get("chapters", ""),
        )
        api_tags = parse_tags_for_api(tags_str)
        pr.white(f"Uploading: {meta['title']}...")
        pr.bip()

        try:
            video_id = upload_video(
                youtube,
                path,
                meta["title"],
                desc,
                api_tags,
                args.lang,
                meta["recording_date"],
            )

            if album:
                if album not in playlist_cache:
                    found = find_existing_playlist(youtube, album)
                    if found is None:
                        pr.no(
                            f"Playlist '{album}' not found — create a YouTube playlist "
                            f"with that exact name or rename the subfolder to match."
                        )
                        raise SystemExit(1)
                    playlist_cache[album] = found

                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_cache[album],
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id,
                            },
                        }
                    },
                ).execute()
                pr.white(f"Added to playlist: {album}")

            # Thumbnail upload logic
            cover_stem = unicodedata.normalize("NFC", path.stem)
            cover_path = Path("output/covers") / path.parent.name / f"{cover_stem}.jpg"
            if cover_path.exists():
                try:
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(
                            str(cover_path), mimetype="image/jpeg", resumable=True
                        ),
                    ).execute()
                    pr.yes(f"    Thumbnail set: {cover_path.name}")
                except Exception as thumb_err:
                    pr.amber(f"    Thumbnail upload failed (non-fatal): {thumb_err}")

            confirm_and_save_nested(
                HISTORY_PATH,
                args.lang,
                history,
                make_history_key(path, album),
                video_id,
                "YouTube",
            )
        except Exception as e:
            pr.no(f"Upload failed for {path.name}: {e}")
            raise SystemExit(1)

    pr.green("Session complete.")


if __name__ == "__main__":
    main()
