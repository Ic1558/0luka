#!/usr/bin/env python3
# tools/librarian/logger.py
# Librarian Logger — Structured logging (Approved v1)

import os
import json
from pathlib import Path
from tools.librarian.utils import now_utc_iso

def _repo_root() -> Path:
    """Determine repo root relative to this file."""
    return Path(__file__).resolve().parent.parent.parent

def _root() -> Path:
    """Validated ROOT path (Approved v1 / Gate-03)."""
    rr = _repo_root().resolve()
    env = os.environ.get("ROOT")
    if env:
        # Resolve env ROOT and compare to actual repo root
        er = Path(env).expanduser().resolve()
        if er != rr:
            raise SystemExit(
                f"ROOT must match repo root (Approved v1). env ROOT={er} repo_root={rr}"
            )
    return rr

# Log path is strictly relative to validated ROOT
LOG_PATH = _root() / "logs" / "components" / "librarian" / "current.log"

def log_event(event_type: str, detail: dict) -> None:
    """Log a structured event to the component log."""
    entry = {
        "ts_utc": now_utc_iso(),
        "type": event_type,
        **detail
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
