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

```bash
uv run python scripts/gdrive_upload.py --lang ru --dry-run
```

Browser opens → log in as your **Drive Account** → creates `gdrive_token.json`.

---

## Files Reference

| File | Purpose | Commit? |
|------|---------|---------|
| `gdrive_token.json` | Drive Account access token | ⛔ Never |
