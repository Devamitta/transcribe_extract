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

1. Go to "OAuth consent screen" → **Audience** tab.
2. Set User Type: **External** if not already set.
3. Fill in App name ("Dhamma Uploader") and support/developer email under the **Branding** tab.
4. Under **Audience**, set Publishing status to **In production** (not "Testing").

> **Why production?** Apps left in Testing mode issue refresh tokens that expire after 7 days, forcing re-authentication every week or two. Production mode tokens persist until explicitly revoked.

Both the YouTube Account and Drive Account log in separately to authorize the app for their own service — no test-user list needed once the app is in production.

---

## Step 3: Initial YouTube Login

Run a dry-run to trigger the browser OAuth flow:

```fish
uv run python scripts/yt_upload.py --lang ru --dry-run --force --limit 1
uv run python scripts/yt_upload.py --lang en --dry-run --force --limit 1
```

Each shows a token status line, then asks **"Probe API quota? [y/N]:"** — answer `y` to open the browser. Log in as your **YouTube Account** → creates `youtube_token_ru.json` / `youtube_token_en.json`.

> `--force --limit 1` is needed when upload history already exists; without it the script exits before reaching auth.

---

## Files Reference

| File | Purpose | Commit? |
|------|---------|---------|
| `client_secret.json` | OAuth app identity — shared by both services | ⛔ Never |
| `youtube_token_ru.json` | YouTube RU upload token | ⛔ Never |
| `youtube_token_en.json` | YouTube EN upload token | ⛔ Never |
