# YouTube Upload Setup

Auth setup for uploading to YouTube. Both YouTube and Google Drive uploads share the same GCP project — complete this doc first, then follow [upload-gdrive.md](upload-gdrive.md) for Drive setup.

---

## Account Architecture

| Role | Uploads to | Token file |
|------|-----------|-----------|
| **YouTube Account** | YouTube channel | `youtube_token_ru.json` / `youtube_token_en.json` |
| **Drive Account** | Google Drive | `gdrive_token.json` |

Both use the same `client_secret.json` from a single GCP project owned by the YouTube Account.

---

## Step 1: GCP Project Setup (YouTube Account)

1. Log in to [console.cloud.google.com](https://console.cloud.google.com) using your **YouTube Account**.
2. Create a new project named "Dhamma Uploader".
3. Enable APIs:
   - "YouTube Data API v3"
   - "Google Drive API"
4. Create Credentials → OAuth 2.0 Client ID → **Desktop app** → name "Dhamma Uploader".
5. Download the JSON, rename it to `client_secret.json`, place in the project root.

---

## Step 2: OAuth Consent Screen (CRITICAL)

1. Go to "OAuth consent screen" → User Type: **External** → Create.
2. App name: "Dhamma Uploader". Support + developer email: your **YouTube Account**.
3. Click through to **"Test users"** → **Add Users**:
   - Email of your **YouTube Account**
   - Email of your **Drive Account**
4. Save and Finish.

Both accounts must be listed here — each one logs in separately to authorize the OAuth app for its own service.

---

## Step 3: Initial YouTube Login

Run a dry-run to trigger the browser OAuth flow:

```bash
uv run python scripts/yt_upload.py --lang ru --dry-run
uv run python scripts/yt_upload.py --lang en --dry-run
```

Each opens a browser → log in as your **YouTube Account** → creates `youtube_token_ru.json` / `youtube_token_en.json`.

---

## Files Reference

| File | Purpose | Commit? |
|------|---------|---------|
| `client_secret.json` | OAuth app identity — shared by both services | ⛔ Never |
| `youtube_token_ru.json` | YouTube RU upload token | ⛔ Never |
| `youtube_token_en.json` | YouTube EN upload token | ⛔ Never |
