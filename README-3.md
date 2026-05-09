# 🤖 Aditya AI — Telegram Userbot

AI-powered auto-reply bot that acts as you on Telegram while you're offline.
Built with **Pyrofork** + **Gemini 2.5 Flash** + **FastAPI** + **SQLite**.

---

## 🏗️ Stack

| Layer       | Tech                          |
|-------------|-------------------------------|
| Telegram    | Pyrofork (Pyrogram fork)      |
| AI          | Gemini 2.5 Flash (web search) |
| Storage     | SQLite (Render Persistent Disk)|
| Health API  | FastAPI 0.136.1               |
| Deployment  | Render Web Service            |

---

## ⚙️ Setup (3 steps)

### Step 1 — Get Telegram API credentials
1. Go to https://my.telegram.org
2. Create an app → get `API_ID` and `API_HASH`

### Step 2 — Generate Session String (run locally ONCE)
```bash
pip install pyrofork TgCrypto
python generate_session.py
```
Copy the session string — you'll need it for Render.

### Step 3 — Get Gemini API Key
1. Go to https://aistudio.google.com
2. Create an API key

---

## 🚀 Deploy to Render

1. Push this repo to GitHub
2. Create a new **Web Service** on Render
3. Connect your repo
4. Add these environment variables in Render dashboard:

| Key              | Value                    |
|------------------|--------------------------|
| TELEGRAM_API_ID  | from my.telegram.org     |
| TELEGRAM_API_HASH| from my.telegram.org     |
| SESSION_STRING   | from generate_session.py |
| GEMINI_API_KEY   | from aistudio.google.com |
| DB_PATH          | /data/bot.db             |
| PORT             | 8000                     |

5. Render will auto-detect `render.yaml` and create the persistent disk

---

## 🎮 Commands

Use these in **any Telegram chat** (dot prefix):

| Command   | Action                          |
|-----------|---------------------------------|
| `.on`     | Enable AI auto-reply            |
| `.off`    | Disable AI auto-reply           |
| `.status` | Show stats (replies, users, etc)|

---

## ✨ Features

- **Human-like delay** — 2–8 second random delay + typing indicator
- **Per-user memory** — remembers names, location, context per contact
- **Style learning** — silently watches your real replies and learns your style
- **Context summarization** — auto-compresses history after 20 messages
- **Web search** — Gemini can search the web to answer current questions
- **Self notifications** — logs every AI reply to your Saved Messages
- **Media fallback** — graceful reply for photos/stickers/voice notes
- **Persistent storage** — SQLite on Render disk, survives redeploys

---

## 📁 Files

```
main.py             → Pyrogram handlers + FastAPI server
ai.py               → Gemini 2.5 Flash + web search + summarizer
db.py               → SQLite operations
config.py           → Env vars loader
owner_profile.json  → Your personality & context (edit this!)
generate_session.py → Run once locally to get session string
requirements.txt
render.yaml
.env.example
```

---

## 🔐 Security Notes

- Session string = your Telegram login. Never commit it to git.
- Add `.env` to `.gitignore`
- The bot replies only to DMs, not groups
