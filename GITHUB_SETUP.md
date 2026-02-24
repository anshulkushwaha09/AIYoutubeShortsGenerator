# 🚀 GitHub Actions Setup Guide

## AI YouTube Shorts Generator — Fully Automated

This guide sets up the bot to **automatically generate and upload 2 YouTube Shorts every day** using GitHub Actions (free, no server needed).

---

## ✅ Prerequisites Checklist

Before starting, confirm you have these ready locally:

- [x] `python main.py` ran successfully (video generated)
- [x] `python main.py` (without --dry-run) uploaded a video to YouTube
- [x] `token.pickle` file exists in your project folder (from `auth_youtube.py`)
- [x] `client_secret.json` file exists in your project folder

---

## STEP 1 — Create a GitHub Repository

1. Go to **[github.com/new](https://github.com/new)**
2. Set:
   - **Repository name:** `ai-youtube-shorts-bot` (or anything)
   - **Visibility:** `Private` ← important (keeps your code secret)
   - **DO NOT** check "Add README" or any other files
3. Click **Create repository**
4. Copy the repo URL — looks like: `https://github.com/YOUR_USERNAME/ai-youtube-shorts-bot.git`

---

## STEP 2 — Push Your Code to GitHub

Open PowerShell in your project folder and run these commands **one by one:**

```powershell
# 1. Initialise git (skip if repo already has .git folder)
git init

# 2. Set your identity (first time only)
git config user.email "you@example.com"
git config user.name "Your Name"

# 3. Stage all files (.gitignore will automatically exclude secrets)
git add .

# 4. Check what will be committed — VERIFY these files are NOT listed:
#    .env | token.pickle | client_secret.json | venv/
git status

# 5. Commit
git commit -m "Initial commit: AI YouTube Shorts Bot"

# 6. Add your GitHub repo as origin (replace URL with yours)
git remote add origin https://github.com/YOUR_USERNAME/ai-youtube-shorts-bot.git

# 7. Push
git branch -M main
git push -u origin main
```

> ⚠️ If `git status` shows `.env`, `token.pickle`, or `client_secret.json` — **STOP** and check `.gitignore` before continuing.

---

## STEP 3 — Encode `token.pickle` to Base64

GitHub can't store binary files as secrets directly. Convert it with PowerShell:

```powershell
# Run this in your project folder
[Convert]::ToBase64String([IO.File]::ReadAllBytes('token.pickle')) | clip
```

This **copies the encoded token to your clipboard**. You'll paste it in Step 4.

---

## STEP 4 — Add GitHub Secrets

Secrets are encrypted and injected as environment variables during the workflow.

1. Go to your repo on GitHub
2. Click **Settings → Secrets and variables → Actions → New repository secret**
3. Add these **3 secrets** one by one:

| Secret Name         | Where to get the value                                                                |
| ------------------- | ------------------------------------------------------------------------------------- |
| `GEMINI_API_KEY`    | From your `.env` file / [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `PEXELS_API_KEY`    | From your `.env` file / [pexels.com/api](https://www.pexels.com/api/)                 |
| `YOUTUBE_TOKEN_B64` | Paste from clipboard (Step 3 output)                                                  |

**To add each secret:**

- Click **New repository secret**
- Enter the **Name** exactly as shown above (case-sensitive)
- Paste the **Value**
- Click **Add secret**

---

## STEP 5 — Verify the Workflow File

Make sure the workflow file exists in your repo. Check:

```
.github/
  workflows/
    daily_shorts.yml    ← This must be present
```

If you can see it on GitHub at `github.com/YOUR_USERNAME/ai-youtube-shorts-bot/blob/main/.github/workflows/daily_shorts.yml` — you're good.

The workflow is already configured to run:

- **12:00 PM IST** (06:30 UTC) — lunch-time peak
- **8:00 PM IST** (14:30 UTC) — evening prime time

---

## STEP 6 — Test the Workflow Manually

Don't wait until tomorrow — trigger it now:

1. Go to your repo on GitHub
2. Click the **Actions** tab
3. In the left sidebar, click **"Twice-Daily YouTube Shorts"**
4. Click the **"Run workflow"** dropdown button (top right)
5. Click **"Run workflow"** (green button)

Watch the live logs — it should take about **8–12 minutes** to complete. At the end you'll see:

```
✅ Uploaded! Video URL: https://www.youtube.com/shorts/XXXXXX
```

---

## STEP 7 — Verify on YouTube Studio

1. Go to **[studio.youtube.com](https://studio.youtube.com)**
2. Click **Content** in the left sidebar
3. Your new Short should appear at the top

---

## 🔧 Troubleshooting

### ❌ "token.pickle not found"

The `YOUTUBE_TOKEN_B64` secret is wrong. Re-run Step 3 and re-paste into the secret.

### ❌ "GEMINI_API_KEY not set" or quota errors

Check the `GEMINI_API_KEY` secret value. The bot automatically tries 5 different models on quota errors.

### ❌ Workflow not running automatically

- GitHub disables scheduled workflows on repos with no activity for 60 days. Push any commit to re-enable.
- GitHub cron can be up to **15 minutes late** — this is normal.

### ❌ "token expired" / 401 error after a few months

Re-run `python auth_youtube.py` locally, then re-encode `token.pickle` and update the `YOUTUBE_TOKEN_B64` secret.

---

## 📊 What Each Run Does (automatically)

```
GitHub Actions triggers at 12pm / 8pm IST
        ↓
1. Checks out your code
2. Installs FFmpeg + Python packages
3. Injects secrets as environment variables
4. Restores token.pickle from YOUTUBE_TOKEN_B64
5. Runs: python main.py
        ↓
   • gemini-2.5-flash generates today's trending topic + script
   • edge-tts creates the voiceover audio
   • Pexels downloads stock video clips
   • FFmpeg renders scenes with 3D captions
   • FFmpeg stitches the final Short (1080×1920)
   • YouTube API uploads the video
        ↓
6. Archives the MP4 as a GitHub artifact (7-day retention)
```

---

## 🔑 Summary of All Files NOT in GitHub (stored as Secrets)

| File                 | Stored As                                   | Why                                                 |
| -------------------- | ------------------------------------------- | --------------------------------------------------- |
| `.env`               | `GEMINI_API_KEY` + `PEXELS_API_KEY` secrets | API keys                                            |
| `token.pickle`       | `YOUTUBE_TOKEN_B64` secret                  | YouTube OAuth                                       |
| `client_secret.json` | Already in repo...                          | Actually move this to secrets too if repo is public |
| `venv/`              | Re-installed from `requirements.txt`        | Too large for Git                                   |

> ⚠️ **If your repo is PUBLIC:** Also add `client_secret.json` contents as a secret named `YOUTUBE_CLIENT_SECRET` and update the workflow to write it to disk before running.
