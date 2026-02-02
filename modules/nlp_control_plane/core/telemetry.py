"""
Telemetry Logger for NLP Control Plane
======================================
Append events to gateway telemetry log.

COPY EXACT from tools/web_bridge/routers/chat.py lines 131-146
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import json

# ============================================================
# Telemetry Logger
# ============================================================

TELEMETRY_PATH = Path("/Users/icmini/0luka/observability/telemetry/gateway.jsonl")

def log_telemetry(event: str, data: Dict[str, Any]) -> None:
    """Append event to gateway telemetry log."""
    try:
        entry = {
            "ts_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "module": "chat_gateway",
            "event": event,
            **data
        }
        TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Non-critical, don't fail request
