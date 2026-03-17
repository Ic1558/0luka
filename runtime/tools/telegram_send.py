"""AG-P5: Telegram Send Tool — governed tool for sending Telegram messages."""
from __future__ import annotations

import os

import httpx


def telegram_send(payload: dict) -> dict:
    """Send a Telegram message.

    Args:
        payload: {
            "message": str,                    # required
            "bot_token": str | None,           # overrides env var
            "chat_id": str | int | None,       # overrides env var
        }

    Returns:
        {"ok": bool, "message_id": int | None, "error": str | None}
    """
    message = payload.get("message", "")
    if not message:
        return {"ok": False, "message_id": None, "error": "message_empty"}

    bot_token = (payload.get("bot_token")
                 or os.environ.get("TELEGRAM_BOT_TOKEN_GGMESH", "").strip()
                 or os.environ.get("TELEGRAM_BOT_TOKEN_IC_NOTIFY", "").strip())
    chat_id = (payload.get("chat_id")
               or os.environ.get("TELEGRAM_CHAT_ID_GGMESH", "").strip()
               or "-1002324084957")

    if not bot_token:
        return {"ok": False, "message_id": None, "error": "bot_token_missing"}
    if not chat_id:
        return {"ok": False, "message_id": None, "error": "chat_id_missing"}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = httpx.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        msg_id = (data.get("result") or {}).get("message_id")
        return {"ok": True, "message_id": msg_id, "error": None}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "message_id": None, "error": f"http_{exc.response.status_code}:{exc.response.text[:120]}"}
    except Exception as exc:
        return {"ok": False, "message_id": None, "error": str(exc)[:200]}
