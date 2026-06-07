# Google Drive Upload Setup

Auth setup for uploading to Google Drive. Requires GCP project and OAuth consent screen already configured — see [upload-youtube.md](upload-youtube.md) first.

---

## Step 1: Get the Drive Folder ID

1. Log in to Google Drive with your **Drive Account**.
2. Find or create the folder for video/audio backups.
3. Copy the Folder ID from the URL (`.../folders/<FOLDER_ID>`).
4. Add to `.env`:
   ```
   GDRIVE_FOLDER_ID_RU=your_ru_folder_id
   GDRIVE_FOLDER_ID_EN=your_en_folder_id
   ```

---

## Step 2: Initial Drive Login

Run a dry-run to trigger the browser OAuth flow:

```fish
uv run python scripts/gdrive_upload.py --lang ru --dry-run --force --limit 1
```

Browser opens → log in as your **Drive Account** → creates `gdrive_token.json`.

> `--force --limit 1` is needed when upload history already exists; without it the script exits before reaching auth.

Drive upload stores media under `video/` and `audio/` in the configured language root. Video files always go under `video/`; audio files always go under `audio/`. `**Selected Playlist:**` is the only field that can add a subfolder inside those base folders. When one playlist is selected, that playlist name becomes the matching subfolder in both places. When multiple playlists are selected, Drive asks which single subfolder to use. If `Selected Playlist` is blank, no extra subfolder is used.

`yt_run.sh --gdrive` passes `--files-from-log` so Drive upload is limited to media exported in the current run. Direct `gdrive_upload.py` runs without that flag still scan the selected output folder.

---

## Files Reference

| File | Purpose | Commit? |
|------|---------|---------|
| `gdrive_token.json` | Drive Account access token | ⛔ Never |
