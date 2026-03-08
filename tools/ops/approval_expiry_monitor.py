#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import approval_state

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _lane_status(entry: dict[str, Any]) -> str:
    if bool(entry.get("expired")):
        return "EXPIRED"
    if bool(entry.get("expiring_soon")):
        return "EXPIRING_SOON"
    return "OK"


def evaluate_expiry(*, runtime_root: Path | None = None) -> dict[str, Any]:
    resolved_runtime_root = runtime_root or _runtime_root()
    payload = approval_state.load_approval_state(runtime_root=resolved_runtime_root)
    lanes: list[dict[str, Any]] = []
    for lane_name in approval_state.LANES:
        entry = payload["lanes"][lane_name]
        lanes.append(
            {
                "lane": lane_name,
                "actor": entry.get("approved_by"),
                "expires_at": entry.get("expires_at"),
                "status": _lane_status(entry),
                "expired": bool(entry.get("expired")),
                "expiring_soon": bool(entry.get("expiring_soon")),
                "approval_present": bool(entry.get("approval_present")),
            }
        )
    return {
        "ok": True,
        "timestamp": _utc_now(),
        "runtime_root": str(resolved_runtime_root),
        "lanes": lanes,
    }


def _render_human(payload: dict[str, Any]) -> str:
    lines = ["Approval Expiry", "---------------"]
    for row in payload.get("lanes", []):
        lines.append(
            f"{row['lane']}: status={row['status']} actor={row.get('actor') or 'n/a'} "
            f"expires_at={row.get('expires_at') or 'n/a'}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report approval expiry status by lane.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        payload = evaluate_expiry()
    except Exception as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, sort_keys=True))
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(_render_human(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
