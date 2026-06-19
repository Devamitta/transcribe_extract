"""Batch-uploads Dhamma MP4s to YouTube with playlist and history support."""

import argparse
import os
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from googleapiclient.http import MediaFileUpload

from tools.lang import LANG_TO_FOLDER
from tools.printer import printer as pr
from tools.source_scope import path_matches_filter, read_source_filter
from tools.uploader_common import (
    build_description,
    check_api_probe,
    check_token_local,
    execute_resumable_upload,
    format_file_size,
    find_path_by_normalized_name,
    find_mp4s_with_album,
    get_google_client,
    list_channel_playlists,
    load_nested_history,
    make_history_key,
    mark_uploaded,
    match_mp4_to_review,
    parse_review,
    parse_tags_for_api,
    save_nested_history,
    is_uploaded_in_history,
    UPLOAD_CHUNK_SIZE_BYTES,
)


CLIENT_SECRET = Path("client_secret.json")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
HISTORY_PATH = Path("output/youtube_history.json")
DEFAULT_BATCH = 6

TOKEN_PATHS: dict[str, Path] = {
    "ru": Path("youtube_token_ru.json"),
    "en": Path("youtube_token_en.json"),
}


def add_video_to_selected_playlists(
    youtube: Any,
    video_id: str,
    selected_playlists: list[str],
    playlist_ids: dict[str, str],
    video_name: str,
) -> list[str]:
    """Add a video to found selected playlists and warn for missing selections."""
    added: list[str] = []
    for playlist_title in selected_playlists:
        playlist_id = playlist_ids.get(playlist_title)
        if playlist_id is None:
            pr.amber(
                f"Selected playlist '{playlist_title}' not found for {video_name}; "
                "upload continues."
            )
            continue
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id,
                    },
                }
            },
        ).execute()
        added.append(playlist_title)
    return added


def parse_recording_date(date_str: str) -> str | None:
    """Convert DD-MM-YYYY to RFC 3339 for YouTube recordingDate field."""
    try:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime(
            "%Y-%m-%dT00:00:00.000Z"
        )
    except ValueError:
        return None


def compute_publish_at(publish_date: str) -> str:
    """Return RFC 3339 publishAt timestamp.

    If publish_date (DD-MM-YYYY) is a future date (not today), schedule for
    10:00 UTC on that date. Otherwise schedule 10 minutes from now.
    """
    now_utc = datetime.now(timezone.utc)
    if publish_date:
        try:
            target = datetime.strptime(publish_date, "%d-%m-%Y").replace(
                tzinfo=timezone.utc
            )
            target = target.replace(hour=10, minute=0, second=0, microsecond=0)
            today_utc = now_utc.date()
            if target.date() > today_utc:
                return target.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except ValueError:
            pass
    # Default: 10 minutes from now
    fallback = now_utc + timedelta(minutes=10)
    return fallback.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def upload_video(
    youtube: Any,
    mp4_path: Path,
    title: str,
    description: str,
    tags: list[str],
    lang: str,
    recording_date: str = "",
    privacy_status: str = "private",
    publish_at: str | None = None,
) -> str:
    """Uploads a single video to YouTube."""
    media = MediaFileUpload(
        str(mp4_path),
        mimetype="video/mp4",
        chunksize=UPLOAD_CHUNK_SIZE_BYTES,
        resumable=True,
    )
    status_body: dict[str, Any] = {
        "privacyStatus": privacy_status,
        "selfDeclaredMadeForKids": False,
    }
    if publish_at:
        status_body["publishAt"] = publish_at
    body: dict[str, Any] = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "27",  # Education
            "tags": tags,
            "defaultLanguage": lang,
            "defaultAudioLanguage": lang,
        },
        "status": status_body,
    }
    parts = "snippet,status"
    iso_date = parse_recording_date(recording_date) if recording_date else None
    if iso_date:
        body["recordingDetails"] = {"recordingDate": iso_date}
        parts = "snippet,status,recordingDetails"

    request = youtube.videos().insert(part=parts, body=body, media_body=media)
    response = execute_resumable_upload(
        request,
        "    Video upload progress",
        show_speed=True,
    )
    return response["id"]


def main() -> None:
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
    parser.add_argument(
        "--name",
        type=str,
        help="Speaker name override (passed from yt_run.sh; suppresses default bio).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Upload even when YouTube history marks the video uploaded.",
    )
    args = parser.parse_args()
    load_dotenv()

    _bio_key = "BIO_RU" if args.lang == "ru" else "BIO_EN"
    bio_link: str | None = os.environ.get(_bio_key) or None
    # Ariyadhammika Bhikkhu talks: omit recording date from public description
    _include_date = not (args.name and "ariyadhammika" in args.name.lower())

    if args.folder is not None:
        folder_names = [args.folder]
    else:
        folder_names = [LANG_TO_FOLDER[args.lang]]

    if not folder_names:
        pr.no("No subfolders found in 'output/transcribed/'.")
        return

    token_path = TOKEN_PATHS[args.lang]
    history = load_nested_history(HISTORY_PATH, args.lang)

    # Pre-load specific file paths from log (NFC-normalized).
    # Log paths are NFC (built from review strings); find_mp4s_with_album returns
    # NFD paths (macOS APFS) — normalise both sides to NFC at comparison time.
    specific = read_source_filter(args.files_from_log)

    # Gather all pending uploads from selected folders
    all_to_upload: list[tuple[Path, dict, str]] = []
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
        for path, _album in mp4s:
            key = make_history_key(path, None)
            if not args.force and is_uploaded_in_history(history, key):
                # In dry-run with a files-from-log, bypass history for the specific
                # file so the dry-run can show what the upload step would do even
                # when the file is already in history (e.g. testing with a real file).
                if not (
                    args.dry_run
                    and specific is not None
                    and path_matches_filter(path, specific)
                ):
                    continue

            meta = match_mp4_to_review(path, review)
            if meta:
                if meta.get("approved"):
                    all_to_upload.append((path, meta, folder_name))
            else:
                # Only warn if folder was explicitly specified
                if args.folder:
                    pr.amber(
                        f"    Missing metadata for {path.name} in folder '{folder_name}'"
                    )

    if not all_to_upload:
        pr.green("Everything already uploaded.")
        return

    # Restrict to specific files if a created-log was provided.
    if specific is not None:
        all_to_upload = [
            t for t in all_to_upload if path_matches_filter(t[0], specific)
        ]

    if not all_to_upload:
        pr.green("No new uploads for this run.")
        return

    # Sort all pending uploads by recording date.
    # When filtering by log (--from-export re-run), sort newest first so the current video
    # (which has the most recent recording date) is uploaded before any backlog.
    def _parse_date(t: tuple[Path, dict, str]) -> datetime:
        try:
            return datetime.strptime(t[1]["recording_date"], "%d-%m-%Y")
        except (ValueError, KeyError):
            return datetime.min

    newest_first = specific is not None
    all_to_upload.sort(key=_parse_date, reverse=newest_first)

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
        for path, meta, folder_name in to_upload:
            tags_str = meta.get("tags", "")
            desc = build_description(
                meta["recording_date"] if _include_date else "",
                meta["description"],
                tags_str,
                chapters=meta.get("chapters", ""),
                bio_link=bio_link,
            )
            api_tags = parse_tags_for_api(tags_str)
            iso_date = parse_recording_date(meta["recording_date"])
            publish_at = compute_publish_at(meta.get("publish_date", ""))
            privacy_label = "private (scheduled)"
            publish_at_label = publish_at
            pr.white(f"\n  File:           {path}")
            selected_playlists = meta.get("selected_playlists", [])
            playlist_label = (
                ", ".join(selected_playlists) if selected_playlists else "(none)"
            )
            pr.white(f"  Selected playlists: {playlist_label}")
            pr.white(f"  Title:          {meta['title']}")
            pr.white(f"  Language:       {args.lang}")
            pr.white(f"  Privacy status: {privacy_label}")
            pr.white(f"  Publish at:     {publish_at_label}")
            pr.white(
                f"  Recording date: {meta['recording_date']} → {iso_date or 'INVALID DATE'}"
            )
            pr.white(f"  Tags:           {', '.join(api_tags)}")
            pr.white(f"  Description:\n{desc}")
        tok_ok, tok_msg = check_token_local(token_path)
        if tok_ok:
            pr.yes(f"Token: {tok_msg}")
        else:
            pr.no(f"Token: {tok_msg}")
        try:
            answer = input("Probe API quota? [y/N]: ").strip().lower()
        except EOFError:
            answer = ""
        if answer == "y":
            pr.green("Probing YouTube API for quota status...")
            pr.bip()
            yt_probe = get_google_client(
                "youtube", "v3", token_path, SCOPES, CLIENT_SECRET
            )
            ok, msg = check_api_probe(yt_probe)
            if ok:
                pr.yes(msg)
            else:
                pr.no(msg)
        return

    youtube = get_google_client("youtube", "v3", token_path, SCOPES, CLIENT_SECRET)
    playlist_ids = list_channel_playlists(youtube)

    for path, meta, folder_name in to_upload:
        tags_str = meta.get("tags", "")
        desc = build_description(
            meta["recording_date"] if _include_date else "",
            meta["description"],
            tags_str,
            chapters=meta.get("chapters", ""),
            bio_link=bio_link,
        )
        api_tags = parse_tags_for_api(tags_str)
        privacy_status = "private"
        publish_at: str | None = compute_publish_at(meta.get("publish_date", ""))
        pr.white(f"Uploading: {meta['title']}...")
        pr.white(f"    Video size: {format_file_size(path.stat().st_size)}")
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
                privacy_status=privacy_status,
                publish_at=publish_at,
            )

            selected_playlists = meta.get("selected_playlists", [])
            added_playlists = add_video_to_selected_playlists(
                youtube,
                video_id,
                selected_playlists,
                playlist_ids,
                path.name,
            )
            for playlist_title in added_playlists:
                pr.white(f"Added to playlist: {playlist_title}")

            # Thumbnail upload logic
            thumb_was_set = False
            cover_stem = unicodedata.normalize("NFC", path.stem)
            cover_path = find_path_by_normalized_name(
                Path("output/covers") / folder_name, f"{cover_stem}.jpg"
            )
            if cover_path.exists():
                try:
                    thumbnail_request = youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(
                            str(cover_path),
                            mimetype="image/jpeg",
                            chunksize=UPLOAD_CHUNK_SIZE_BYTES,
                            resumable=True,
                        ),
                    )
                    execute_resumable_upload(
                        thumbnail_request,
                        "    Thumbnail upload progress",
                    )
                    pr.yes(f"    Thumbnail set: {cover_path.name}")
                    thumb_was_set = True
                except Exception as thumb_err:
                    pr.amber(f"    Thumbnail upload failed (non-fatal): {thumb_err}")

            hist_key = make_history_key(path, None)
            mark_uploaded(history, hist_key, video_id)
            history[hist_key]["thumbnail_set"] = thumb_was_set  # type: ignore[assignment]
            save_nested_history(HISTORY_PATH, args.lang, history)
            pr.yes(f"Uploaded to YouTube: {hist_key} (ID: {video_id})")
        except Exception as e:
            pr.no(f"Upload failed for {path.name}: {e}")
            raise SystemExit(1)

    pr.green("Session complete.")


if __name__ == "__main__":
    main()
