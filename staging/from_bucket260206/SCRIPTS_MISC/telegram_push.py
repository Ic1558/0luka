import aiohttp
import asyncio
import json
import ssl

async def send_telegram_message():
    token = "7879860258:AAHffCJY3sjOq94or_qOpvZHS8PhvP4MMqM"
    chat_id = "-1002324084957"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": "✅ Push ผ่าน aiohttp แบบไม่ verify SSL สำเร็จแล้ว!"}

    # ข้าม SSL Verification (ชั่วคราว)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, ssl=ssl_context, timeout=10) as response:
                result = await response.json()
                print(json.dumps(result, indent=2))
                return result
    except Exception as e:
        print({"error": str(e)})
        return {"error": str(e)}

if __name__ == "__main__":
    asyncio.run(send_telegram_message())

