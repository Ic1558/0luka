import aiohttp
import asyncio
import json

async def send_telegram_message():
    token = "7879860258:AAHffCJY3sjOq94or_qOpvZHS8PhvP4MMqM"
    chat_id = "-1002324084957"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": "Test message from Grok - Attempt 5"} 
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as response:
                result = await response.json()
                with open("telegram_test_result.json", "w") as f:
                    json.dump(result, f, indent=2)
                print(result)
                return result
    except Exception as e:
        error = {"error": str(e)}
        with open("telegram_test_error.json", "w") as f:
            json.dump(error, f, indent=2)
        print(error)
        return error

if __name__ == "__main__":
    asyncio.run(send_telegram_message())

