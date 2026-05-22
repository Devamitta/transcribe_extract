"""Batch-uploads Dhamma MP4s to Google Drive preserving folder structure."""

import argparse
import os
import pickle
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from tools.printer import printer as pr
from tools.uploader_common import (
    build_description,
    confirm_and_save_nested,
    find_audio_for_mp4,
    find_mp4s_with_album,
    gdrive_folder_env_key,
    load_nested_history,
    make_history_key,
    match_mp4_to_review,
    parse_review,
)


CLIENT_SECRET = Path("client_secret.json")
TOKEN_PATH = Path("gdrive_token.json")
SCOPES = [
    "https://www.googleapis.com/auth/drive",
]
GDRIVE_HISTORY_PATH = Path("output/gdrive_history.json")
LEGACY_VIDEO_HISTORY = Path("output/gdrive_video_history.json")
LEGACY_AUDIO_HISTORY = Path("output/gdrive_audio_history.json")
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
LANG_TO_FOLDER: dict[str, str] = {"ru": "russian", "en": "english"}


def get_google_client(service: str, version: str):
    """Authenticates and returns a Google API client."""
    creds: Credentials | None = None
    if TOKEN_PATH.exists():
        with TOKEN_PATH.open("rb") as f:
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
        with TOKEN_PATH.open("wb") as f:
            pickle.dump(creds, f)
    return build(service, version, credentials=creds)


def get_or_create_folder(drive, parent_id: str, name: str) -> str:
    """Finds or creates a Google Drive folder by name."""
    query = (
        f"name='{name}' and mimeType='{DRIVE_FOLDER_MIME}'"
        f" and '{parent_id}' in parents and trashed=false"
    )
    response = drive.files().list(q=query, fields="files(id,name)").execute()
    files = response.get("files", [])
    if files:
        return files[0]["id"]
    created = (
        drive.files()
        .create(
            body={"name": name, "mimeType": DRIVE_FOLDER_MIME, "parents": [parent_id]},
            fields="id",
        )
        .execute()
    )
    pr.green(f"Created Drive folder: {name}")
    return created["id"]


def upload_file(
    drive,
    file_path: Path,
    folder_id: str,
    filename: str,
    description: str,
    mimetype: str = "video/mp4",
) -> str:
    """Uploads a single file to Google Drive."""
    media = MediaFileUpload(str(file_path), mimetype=mimetype, resumable=True)
    response = (
        drive.files()
        .create(
            body={
                "name": filename,
                "parents": [folder_id],
                "description": description,
            },
            media_body=media,
            fields="id",
        )
        .execute()
    )
    return response["id"]


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Batch-uploads Dhamma MP4s to Google Drive preserving folder structure."
    )
    parser.add_argument(
        "--lang",
        type=str,
        required=True,
        choices=["ru", "en"],
        help="Language of the talk (ru|en).",
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Subfolder name (e.g. 'russian', 'english'). If absent, processes all folders.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not upload, just list"
    )
    parser.add_argument(
        "--batch-size", type=int, default=0, help="Max uploads (0=unlimited)"
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
        "--audio-dir",
        type=Path,
        help="Override source MP3 directory",
    )
    args = parser.parse_args()

    env_key = gdrive_folder_env_key(args.lang)
    root_folder_id = os.getenv(env_key)
    if not root_folder_id:
        pr.no(f"{env_key} not set in .env")
        return

    transcribed_base = Path("output/transcribed")
    if args.folder:
        folder_names = [args.folder]
    else:
        folder_names = [d.name for d in transcribed_base.iterdir() if d.is_dir()]

    if not folder_names:
        pr.no("No subfolders found in 'output/transcribed/'.")
        return

    video_history = load_nested_history(
        GDRIVE_HISTORY_PATH, args.lang, "video", legacy_path=LEGACY_VIDEO_HISTORY
    )
    audio_history = load_nested_history(
        GDRIVE_HISTORY_PATH, args.lang, "audio", legacy_path=LEGACY_AUDIO_HISTORY
    )

    all_to_upload: list[tuple[Path, str | None, dict, Path, Path]] = []
    lang_folder = LANG_TO_FOLDER.get(args.lang or "en", "english")
    for folder_name in folder_names:
        review_path = args.review_file or Path("reviews") / f"{lang_folder}_review.md"
        if not review_path or not review_path.exists():
            continue

        review = parse_review(review_path)
        input_dir = args.input_dir or Path("output/video") / folder_name
        audio_dir = args.audio_dir or Path("output/audio") / folder_name

        if not input_dir.exists():
            continue

        mp4s = find_mp4s_with_album(input_dir)
        for path, album in mp4s:
            key = make_history_key(path, album)
            if key in video_history and video_history[key].get("status") == "uploaded":
                continue

            meta = match_mp4_to_review(path, review)
            if meta:
                all_to_upload.append((path, album, meta, input_dir, audio_dir))
            else:
                if args.folder:
                    pr.amber(
                        f"    Missing metadata for {path.name} in folder '{folder_name}'"
                    )

    if not all_to_upload:
        pr.green("Everything already uploaded.")
        return

    if args.limit > 0:
        to_upload = all_to_upload[: args.limit]
    elif args.batch_size > 0:
        to_upload = all_to_upload[: args.batch_size]
    else:
        to_upload = all_to_upload

    pr.green(f"{len(to_upload)} video(s) queued for Google Drive upload.")

    if args.dry_run:
        pr.green_title(
            f"[DRY-RUN] Found {len(to_upload)} videos to upload to Drive (Folder ID: {root_folder_id}):"
        )
        for path, album, meta, _in_dir, audio_dir in to_upload:
            tags_str = meta.get("tags", "")
            desc = build_description(
                meta["recording_date"], meta["description"], tags_str
            )
            audio_path = find_audio_for_mp4(path, audio_dir)
            video_dest = f"video/{album}/{path.name}" if album else f"video/{path.name}"
            pr.white(f"\n  File:        {path.name}")
            pr.white(f"  Folder:      {video_dest}")
            pr.white(f"  Title:       {meta['title']}")
            pr.white(f"  Date:        {meta['recording_date']}")
            pr.white(f"  Description:\n{desc}")
            if audio_path:
                audio_dest = (
                    f"audio/{album}/{audio_path.name}"
                    if album
                    else f"audio/{audio_path.name}"
                )
                pr.white(f"  Audio:       {audio_dest}")
            else:
                pr.white(f"  Audio:       not found in {audio_dir}")
        return

    drive = get_google_client("drive", "v3")
    folder_cache: dict[str, str] = {}

    for path, album, meta, _in_dir, audio_dir in to_upload:
        tags_str = meta.get("tags", "")
        desc = build_description(meta["recording_date"], meta["description"], tags_str)

        # video/ top-level folder
        if "video" not in folder_cache:
            folder_cache["video"] = get_or_create_folder(drive, root_folder_id, "video")
        video_root = folder_cache["video"]

        # audio/ top-level folder
        if "audio" not in folder_cache:
            folder_cache["audio"] = get_or_create_folder(drive, root_folder_id, "audio")
        audio_root = folder_cache["audio"]

        # album subfolder inside video/ and audio/ (if applicable)
        if album:
            video_album_key = f"video|{album}"
            if video_album_key not in folder_cache:
                folder_cache[video_album_key] = get_or_create_folder(
                    drive, video_root, album
                )
            video_folder = folder_cache[video_album_key]

            audio_album_key = f"audio|{album}"
            if audio_album_key not in folder_cache:
                folder_cache[audio_album_key] = get_or_create_folder(
                    drive, audio_root, album
                )
            audio_folder = folder_cache[audio_album_key]
        else:
            video_folder = video_root
            audio_folder = audio_root

        pr.white(f"Uploading to Drive: {path.name}...")
        pr.bip()

        try:
            file_id = upload_file(drive, path, video_folder, path.name, desc)
            confirm_and_save_nested(
                GDRIVE_HISTORY_PATH,
                args.lang,
                video_history,
                make_history_key(path, album),
                file_id,
                "Google Drive video",
                section="video",
            )
        except Exception as e:
            pr.no(f"Drive upload failed for {path.name}: {e}")
            continue

        audio_path = find_audio_for_mp4(path, audio_dir)
        if audio_path:
            audio_key = make_history_key(audio_path, album)
            if (
                audio_key in audio_history
                and audio_history[audio_key].get("status") == "uploaded"
            ):
                pr.green(f"Audio already uploaded: {audio_path.name}")
            else:
                pr.white(f"Uploading audio to Drive: {audio_path.name}...")
                pr.bip()
                try:
                    audio_id = upload_file(
                        drive,
                        audio_path,
                        audio_folder,
                        audio_path.name,
                        desc,
                        "audio/mpeg",
                    )
                    confirm_and_save_nested(
                        GDRIVE_HISTORY_PATH,
                        args.lang,
                        audio_history,
                        audio_key,
                        audio_id,
                        "Google Drive audio",
                        section="audio",
                    )
                except Exception as e:
                    pr.no(f"Audio upload failed for {audio_path.name}: {e}")

    pr.green("Session complete.")


if __name__ == "__main__":
    main()
