from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional


def dispatch_via_redis(task: Dict[str, Any], request_channel: str, response_channel: str, timeout_s: int = 30) -> Dict[str, Any]:
    try:
        import redis  # type: ignore
    except Exception:
        return {
            "ok": False,
            "status": "FAILED",
            "error": "redis_client_missing",
            "exit_code": 125,
        }

    client = redis.Redis.from_url(task.get("redis_url", "redis://127.0.0.1:6379/0"), decode_responses=True)
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(response_channel)
    client.publish(request_channel, json.dumps(task, sort_keys=True))

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msg: Optional[Dict[str, Any]] = pubsub.get_message(timeout=1.0)
        if msg and msg.get("type") == "message":
            try:
                data = json.loads(msg.get("data") or "{}")
            except Exception:
                data = {"raw": msg.get("data")}
            code = int(data.get("exit_code", 1))
            return {
                "ok": code == 0,
                "status": "DONE" if code == 0 else "FAILED",
                "exit_code": code,
                "response": data,
            }
    return {
        "ok": False,
        "status": "FAILED",
        "error": "response_timeout",
        "exit_code": 124,
    }
