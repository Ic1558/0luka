import redis
import requests
import json
import os

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = "@TFEX_Alerts"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, json=payload)

def listen_redis():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('task:tfex-signal')
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            alert = f"[TFEX Alert] {data['action']} {data['symbol']} (Volume: {data['volume']})"
            send_telegram_message(alert)

if __name__ == "__main__":
    listen_redis()cd ~/Desktop/ggmeshv2
touch push_notify.py
nano push_notify.py
