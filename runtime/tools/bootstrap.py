"""AG-P5: Tool Bootstrap — registers all governed tools into the registry."""
from __future__ import annotations

from runtime.tools.registry import register_tool
from runtime.tools.telegram_send import telegram_send


def bootstrap_tools() -> list[str]:
    """Register all tools. Returns list of registered names."""
    register_tool(
        "telegram_send",
        telegram_send,
        description="Send a Telegram message via Bot API using IC_NOTIFY credentials.",
        schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "bot_token": {"type": "string"},
                "chat_id": {"type": "string"},
            },
            "required": ["message"],
        },
    )
    return ["telegram_send"]
