"""
Aditya's AI Telegram Userbot
─────────────────────────────
Commands (any chat, dot prefix):
  .on      → enable AI auto-reply
  .off     → disable AI auto-reply
  .status  → show stats
"""

import asyncio
import random

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

import ai
import db
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, SESSION_STRING, PORT


# ─── FastAPI Health Server ─────────────────────────────────────────────────────

server = FastAPI()

@server.get("/health")
async def health():
    stats = await db.get_stats()
    return JSONResponse({"status": "ok", **stats})


# ─── Pyrogram Client ───────────────────────────────────────────────────────────

app = Client(
    name="aditya_ai",
    api_id=TELEGRAM_API_ID,
    api_hash=TELEGRAM_API_HASH,
    session_string=SESSION_STRING,
)

# ── In-memory helpers ──────────────────────────────────────────────────────────
# Last incoming message per chat (for style learning)
_last_incoming: dict[int, str] = {}

# Chat IDs where the bot just sent an AI reply
# (so we don't accidentally learn the bot's own reply as owner's style)
_bot_replied: set[int] = set()

# Cached owner's own Telegram user ID (set on startup)
_my_id: int = 0


# ─── Command + Style Learning Handler (messages sent BY ME) ───────────────────

@app.on_message(filters.me & filters.text)
async def handle_my_messages(client: Client, message: Message):
    text = message.text.strip()
    chat_id = message.chat.id

    # ── Commands (dot prefix, any chat) ───────────────────────────────────────
    if text.startswith("."):
        cmd = text.lower()

        if cmd == ".on":
            await db.set_state("active", "true")
            await message.reply("🟢 **AI Reply: ON**")

        elif cmd == ".off":
            await db.set_state("active", "false")
            await message.reply("🔴 **AI Reply: OFF**")

        elif cmd == ".status":
            s = await db.get_stats()
            icon = "🟢" if s["active"] else "🔴"
            await message.reply(
                f"**🤖 Bot Status**\n\n"
                f"{icon} Active: {'Yes' if s['active'] else 'No'}\n"
                f"💬 AI Replies Sent: **{s['total_replies']}**\n"
                f"👥 Unique Users Chatted: **{s['unique_users']}**\n"
                f"🧠 Style Examples Learned: **{s['style_learned']}**"
            )
        return

    # ── Style Learning (private chats only, not Saved Messages) ───────────────
    if message.chat.type == ChatType.PRIVATE and chat_id != _my_id:
        if chat_id in _bot_replied:
            # This outgoing msg is the bot's own reply — don't learn it
            _bot_replied.discard(chat_id)
            return
        # Owner is replying manually → learn the style!
        if chat_id in _last_incoming:
            await db.add_style_example(_last_incoming.pop(chat_id), text)


# ─── Incoming DM Handler ──────────────────────────────────────────────────────

@app.on_message(filters.private & ~filters.me & filters.text)
async def handle_dm(client: Client, message: Message):
    user_id   = message.from_user.id
    user_name = message.from_user.first_name or "Unknown"
    incoming  = message.text

    # Always track for style learning (even when bot is OFF)
    _last_incoming[user_id] = incoming

    # Check if bot is active
    if await db.get_state("active") != "true":
        return

    # ── Ensure user exists & extract any personal info they shared ────────────
    user_profile = await db.get_or_create_user(user_id, user_name)
    extracted    = await ai.extract_user_info(incoming)
    if extracted:
        await db.update_user_info(user_id, extracted)
        user_profile = await db.get_or_create_user(user_id, user_name)

    # ── Fetch history & style examples ───────────────────────────────────────
    history       = await db.get_history(user_id)
    style_samples = await db.get_style_examples()

    # ── Human-like delay + typing indicator ──────────────────────────────────
    await asyncio.sleep(random.uniform(2, 6))

    async with client.action(message.chat.id, "typing"):
        await asyncio.sleep(random.uniform(1, 3))
        reply_text = await ai.generate_reply(
            user_id, incoming, history, user_profile, style_samples
        )

    # ── Send reply ────────────────────────────────────────────────────────────
    await message.reply(reply_text)
    _bot_replied.add(user_id)  # mark so style learner skips this

    # ── Persist to DB ─────────────────────────────────────────────────────────
    await db.add_message(user_id, "user",      incoming)
    await db.add_message(user_id, "assistant", reply_text)
    await db.increment_replies()

    # ── Notify owner via Saved Messages ──────────────────────────────────────
    await client.send_message(
        "me",
        f"🤖 **AI replied to {user_name}**\n"
        f"┌ They: _{incoming[:120]}_\n"
        f"└ Bot: _{reply_text[:120]}_",
    )


# ─── Media / Non-text DM Handler ──────────────────────────────────────────────

@app.on_message(filters.private & ~filters.me & ~filters.text)
async def handle_media(client: Client, message: Message):
    if await db.get_state("active") != "true":
        return

    await asyncio.sleep(random.uniform(3, 7))

    fallbacks = [
        "bhai abhi dekh nahi sakta, baad mein baat karte hain 👀",
        "haan dekha, thoda busy hoon — baad mein reply karta",
        "arrey bhai, baad mein 🙏",
    ]
    await message.reply(random.choice(fallbacks))


# ─── Entry Point ──────────────────────────────────────────────────────────────

async def main():
    global _my_id

    await db.init_db()
    await app.start()

    me = await app.get_me()
    _my_id = me.id
    print(f"✅ Userbot started as @{me.username} (id={me.id})")
    print(f"🌐 Health server starting on port {PORT}")

    uvi_config = uvicorn.Config(server, host="0.0.0.0", port=PORT, log_level="warning")
    uvi_server = uvicorn.Server(uvi_config)
    await uvi_server.serve()

    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
