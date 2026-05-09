"""
Run this script ONCE locally to generate your Pyrogram session string.
Copy the output and paste it as SESSION_STRING in Render env vars.

Usage:
    pip install pyrofork TgCrypto
    python generate_session.py
"""

from pyrogram import Client

API_ID   = int(input("Enter your Telegram API ID: ").strip())
API_HASH = input("Enter your Telegram API Hash: ").strip()

with Client(":memory:", api_id=API_ID, api_hash=API_HASH) as client:
    session_string = client.export_session_string()

print("\n" + "="*60)
print("✅ YOUR SESSION STRING (copy this to Render env vars):\n")
print(session_string)
print("="*60)
print("\nKeep this secret — it's basically your Telegram login!\n")
