"""
Aditya's AI Telegram Userbot
─────────────────────────────
Commands:
  .on      → enable AI auto-reply
  .off     → disable AI auto-reply
  .status  → show stats
"""

import asyncio

# Python 3.14 compatibility fix for Pyrofork
asyncio.set_event_loop(asyncio.new_event_loop())

import random
import signal

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatType
from pyrogram.types import Message

import ai
import db
from config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    SESSION_STRING,
    PORT,
)

# ─────────────────────────────────────────────────────────────
# FastAPI Server
# ─────────────────────────────────────────────────────────────

server = FastAPI()


@server.get("/")
async def root():
    return {"status": "running"}


@server.get("/health")
async def health():
    stats = await db.get_stats()
    return JSONResponse({
        "status": "ok",
        **stats
    })


# ─────────────────────────────────────────────────────────────
# Pyrogram Client
# ─────────────────────────────────────────────────────────────

app = Client(
    name="aditya_ai",
    api_id=TELEGRAM_API_ID,
    api_hash=TELEGRAM_API_HASH,
    session_string=SESSION_STRING,
)

# ─────────────────────────────────────────────────────────────
# Runtime Memory
# ─────────────────────────────────────────────────────────────

_last_incoming: dict[int, str] = {}
_bot_replied: set[int] = set()
_my_id: int = 0


# ─────────────────────────────────────────────────────────────
# Commands + Style Learning
# ─────────────────────────────────────────────────────────────

@app.on_message(filters.me & filters.text)
async def handle_my_messages(client: Client, message: Message):

    text = message.text.strip()
    chat_id = message.chat.id

    # ─── Commands ────────────────────────────────────────────

    if text.startswith("."):

        cmd = text.lower()

        if cmd == ".on":
            await db.set_state("active", "true")
            await message.reply("🟢 AI Reply Enabled")

        elif cmd == ".off":
            await db.set_state("active", "false")
            await message.reply("🔴 AI Reply Disabled")

        elif cmd == ".status":

            s = await db.get_stats()

            await message.reply(
                f"🤖 Bot Status\n\n"
                f"Active: {s['active']}\n"
                f"Replies: {s['total_replies']}\n"
                f"Users: {s['unique_users']}\n"
                f"Style Memory: {s['style_learned']}"
            )

        return

    # ─── Style Learning ──────────────────────────────────────

    if message.chat.type == ChatType.PRIVATE and chat_id != _my_id:

        if chat_id in _bot_replied:
            _bot_replied.discard(chat_id)
            return

        if chat_id in _last_incoming:
            await db.add_style_example(
                _last_incoming.pop(chat_id),
                text
            )


# ─────────────────────────────────────────────────────────────
# Incoming DM Handler
# ─────────────────────────────────────────────────────────────

@app.on_message(filters.private & ~filters.me & filters.text)
async def handle_dm(client: Client, message: Message):

    try:

        user_id = message.from_user.id
        user_name = message.from_user.first_name or "Unknown"
        incoming = message.text

        _last_incoming[user_id] = incoming

        # Bot OFF
        if await db.get_state("active") != "true":
            return

        # User Profile
        user_profile = await db.get_or_create_user(
            user_id,
            user_name
        )

        extracted = await ai.extract_user_info(incoming)

        if extracted:
            await db.update_user_info(user_id, extracted)
            user_profile = await db.get_or_create_user(
                user_id,
                user_name
            )

        # Context
        history = await db.get_history(user_id)
        style_samples = await db.get_style_examples()

        # Human delay
        await asyncio.sleep(random.uniform(2, 5))

        async with client.action(message.chat.id, "typing"):

            await asyncio.sleep(random.uniform(1, 2))

            reply_text = await ai.generate_reply(
                user_id=user_id,
                incoming=incoming,
                history=history,
                user_profile=user_profile,
                style_examples=style_samples,
            )

        # Empty safety
        if not reply_text:
            return

        # Send reply
        await message.reply(reply_text)

        _bot_replied.add(user_id)

        # Save history
        await db.add_message(user_id, "user", incoming)
        await db.add_message(user_id, "assistant", reply_text)

        await db.increment_replies()

        # Notify Saved Messages
        await client.send_message(
            "me",
            f"🤖 AI replied to {user_name}\n\n"
            f"👤 {incoming[:100]}\n\n"
            f"🤖 {reply_text[:100]}"
        )

    except Exception as e:
        print(f"DM Handler Error: {e}")


# ─────────────────────────────────────────────────────────────
# Media Handler
# ─────────────────────────────────────────────────────────────

@app.on_message(filters.private & ~filters.me & ~filters.text)
async def handle_media(client: Client, message: Message):

    try:

        if await db.get_state("active") != "true":
            return

        replies = [
            "bhai abhi dekh nahi sakta 👀",
            "baad mein check karta",
            "busy hoon thoda 😭",
        ]

        await asyncio.sleep(random.uniform(2, 5))

        await message.reply(random.choice(replies))

    except Exception as e:
        print(f"Media Handler Error: {e}")


# ─────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────

async def start_pyrogram():

    global _my_id

    try:

        print("🚀 Starting Pyrogram...")

        await app.start()

        print("✅ LOGIN SUCCESS")

        me = await app.get_me()

        _my_id = me.id

        print(f"✅ Logged in as @{me.username}")
        print(f"🆔 My ID: {_my_id}")

        await idle()

    except Exception as e:

        print(f"❌ PYROGRAM ERROR: {e}")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

async def main():

    print("🧠 Initializing database...")

    await db.init_db()

    # Start Telegram in background
    asyncio.create_task(start_pyrogram())

    print(f"🌐 Starting FastAPI on port {PORT}")

    config = uvicorn.Config(
        app=server,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )

    server_instance = uvicorn.Server(config)

    await server_instance.serve()


# ─────────────────────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):
        print("🛑 Shutting down...")
