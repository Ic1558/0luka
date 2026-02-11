from dotenv import load_dotenv
import os

load_dotenv()  # โหลดค่า .env

REDIS_URL = os.getenv("REDIS_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AGENT_NAME = os.getenv("AGENT_NAME")

print(f"REDIS_URL={REDIS_URL}")
print(f"TELEGRAM_BOT_TOKEN={TELEGRAM_BOT_TOKEN}")
print(f"TELEGRAM_CHAT_ID={TELEGRAM_CHAT_ID}")
print(f"AGENT_NAME={AGENT_NAME}")
