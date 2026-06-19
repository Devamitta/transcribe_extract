"""Batch-uploads Dhamma MP4s to Google Drive preserving folder structure."""

import argparse
from collections.abc import Callable
import os
import pickle
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from tools.lang import LANG_TO_FOLDER
from tools.printer import printer as pr
from tools.source_scope import path_matches_filter, read_source_filter
from tools.uploader_common import (
    UPLOAD_CHUNK_SIZE_BYTES,
    build_description,
    confirm_and_save_nested,
    execute_resumable_upload,
    find_audio_for_mp4,
    find_mp4s_with_album,
    format_file_size,
    gdrive_folder_env_key,
    is_uploaded_key_in_history,
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


def prompt_for_drive_subfolder(
    playlists: list[str],
    media_name: str,
    input_func: Callable[[str], str] = input,
) -> str:
    """Asks which selected playlist should be used as the single Drive folder."""
    pr.amber(f"Multiple selected playlists for Google Drive upload: {media_name}")
    for index, playlist in enumerate(playlists, start=1):
        pr.white(f"  {index}. {playlist}")

    while True:
        choice = input_func("Choose one Drive folder number: ").strip()
        if choice.isdecimal():
            selected_index = int(choice) - 1
            if 0 <= selected_index < len(playlists):
                return playlists[selected_index]
        pr.amber(f"Enter a number from 1 to {len(playlists)}.")


def resolve_drive_subfolder(
    meta: dict[str, Any],
    media_name: str = "media file",
    input_func: Callable[[str], str] = input,
) -> str | None:
    """Returns the optional Google Drive subfolder from the selected playlist field."""
    selected_playlists = meta.get("selected_playlists", [])
    playlists: list[str] = []
    if isinstance(selected_playlists, list):
        playlists = [
            playlist.strip()
            for playlist in selected_playlists
            if isinstance(playlist, str) and playlist.strip()
        ]
    if len(playlists) == 1:
        return playlists[0]
    if len(playlists) > 1:
        return prompt_for_drive_subfolder(playlists, media_name, input_func)
    return None


def get_google_client(service: str, version: str) -> Any:
    """Authenticates and returns a Google API client."""
    creds: Credentials | None = None
    if TOKEN_PATH.exists():
        with TOKEN_PATH.open("rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except google.auth.exceptions.RefreshError:
                pr.amber("Drive token revoked — re-authenticating")
                TOKEN_PATH.unlink(missing_ok=True)
                creds = None
        if not creds or not creds.valid:
            if not CLIENT_SECRET.exists():
                pr.no(f"Missing {CLIENT_SECRET}. Follow output/UPLOAD_SETUP.md")
                raise SystemExit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)  # type: ignore[assignment]
        with TOKEN_PATH.open("wb") as f:
            pickle.dump(creds, f)
    return build(service, version, credentials=creds)


def get_or_create_folder(drive: Any, parent_id: str, name: str) -> str:
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
    drive: Any,
    file_path: Path,
    folder_id: str,
    filename: str,
    description: str,
    mimetype: str = "video/mp4",
    progress_label: str = "    Drive upload progress",
) -> str:
    """Uploads a single file to Google Drive."""
    media = MediaFileUpload(
        str(file_path),
        mimetype=mimetype,
        chunksize=UPLOAD_CHUNK_SIZE_BYTES,
        resumable=True,
    )
    request = drive.files().create(
        body={
            "name": filename,
            "parents": [folder_id],
            "description": description,
        },
        media_body=media,
        fields="id",
    )
    response = execute_resumable_upload(request, progress_label, show_speed=True)
    return response["id"]


def main() -> None:
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Upload even when Drive history marks the file uploaded.",
    )
    parser.add_argument(
        "--files-from-log",
        type=Path,
        help="Only upload media files listed in this log (one path per line).",
    )
    args = parser.parse_args()
    file_filter = read_source_filter(args.files_from_log)

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

    all_to_upload: list[tuple[Path, str | None, dict[str, Any], Path, Path]] = []
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
        for path, _album in mp4s:
            if not path_matches_filter(path, file_filter):
                continue
            meta = match_mp4_to_review(path, review)
            if meta:
                drive_subfolder = resolve_drive_subfolder(meta, path.name)
                key = make_history_key(path, drive_subfolder)
                if not args.force and is_uploaded_key_in_history(video_history, key):
                    continue

                all_to_upload.append(
                    (path, drive_subfolder, meta, input_dir, audio_dir)
                )
            else:
                if args.folder:
                    pr.amber(
                        f"    Missing metadata for {path.name} in folder '{folder_name}'"
                    )

    if not all_to_upload:
        if file_filter is None:
            pr.green("Everything already uploaded.")
        else:
            pr.green("No new Drive uploads for this run.")
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
        for path, drive_subfolder, meta, _in_dir, audio_dir in to_upload:
            tags_str = meta.get("tags", "")
            desc = build_description(
                meta["recording_date"], meta["description"], tags_str
            )
            audio_path = find_audio_for_mp4(path, audio_dir)
            video_dest = (
                f"video/{drive_subfolder}/{path.name}"
                if drive_subfolder
                else f"video/{path.name}"
            )
            pr.white(f"\n  File:        {path.name}")
            pr.white(f"  Folder:      {video_dest}")
            pr.white(f"  Title:       {meta['title']}")
            pr.white(f"  Date:        {meta['recording_date']}")
            pr.white(f"  Description:\n{desc}")
            if audio_path:
                audio_dest = (
                    f"audio/{drive_subfolder}/{audio_path.name}"
                    if drive_subfolder
                    else f"audio/{audio_path.name}"
                )
                pr.white(f"  Audio:       {audio_dest}")
            else:
                pr.white(f"  Audio:       not found in {audio_dir}")
        return

    drive = get_google_client("drive", "v3")
    folder_cache: dict[str, str] = {}

    for path, drive_subfolder, meta, _in_dir, audio_dir in to_upload:
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

        # Selected playlist subfolder inside video/ and audio/ (if applicable)
        if drive_subfolder:
            video_subfolder_key = f"video|{drive_subfolder}"
            if video_subfolder_key not in folder_cache:
                folder_cache[video_subfolder_key] = get_or_create_folder(
                    drive, video_root, drive_subfolder
                )
            video_folder = folder_cache[video_subfolder_key]

            audio_subfolder_key = f"audio|{drive_subfolder}"
            if audio_subfolder_key not in folder_cache:
                folder_cache[audio_subfolder_key] = get_or_create_folder(
                    drive, audio_root, drive_subfolder
                )
            audio_folder = folder_cache[audio_subfolder_key]
        else:
            video_folder = video_root
            audio_folder = audio_root

        pr.white(f"Uploading to Drive: {path.name}...")
        pr.white(f"    Video size: {format_file_size(path.stat().st_size)}")
        pr.bip()

        try:
            file_id = upload_file(
                drive,
                path,
                video_folder,
                path.name,
                desc,
                progress_label="    Drive video upload progress",
            )
            confirm_and_save_nested(
                GDRIVE_HISTORY_PATH,
                args.lang,
                video_history,
                make_history_key(path, drive_subfolder),
                file_id,
                "Google Drive video",
                section="video",
            )
        except Exception as e:
            pr.no(f"Drive upload failed for {path.name}: {e}")
            raise SystemExit(1)

        audio_path = find_audio_for_mp4(path, audio_dir)
        if audio_path:
            audio_key = make_history_key(audio_path, drive_subfolder)
            if is_uploaded_key_in_history(audio_history, audio_key):
                pr.green(f"Audio already uploaded: {audio_path.name}")
            else:
                pr.white(f"Uploading audio to Drive: {audio_path.name}...")
                pr.white(
                    f"    Audio size: {format_file_size(audio_path.stat().st_size)}"
                )
                pr.bip()
                try:
                    audio_id = upload_file(
                        drive,
                        audio_path,
                        audio_folder,
                        audio_path.name,
                        desc,
                        "audio/mpeg",
                        progress_label="    Drive audio upload progress",
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
                    raise SystemExit(1)

    pr.green("Session complete.")


if __name__ == "__main__":
    main()
