import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

DB_PATH = os.getenv("DB_PATH", "bot.db")

PORT = int(os.getenv("PORT", 8000))
