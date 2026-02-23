#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List


def now_utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_files(root: Path, pattern: str) -> List[Path]:
    paths = list(root.glob(pattern))
    return [path for path in paths if path.is_file()]


def run_once(root: Path) -> None:
    processor_path = root / "tools" / "bridge_task_processor.py"
    inbox_pattern = "observability/bridge/inbox/**/*.json"
    inflight_pattern = "observability/bridge/inflight/**/*.json"
    outbox_pattern = "observability/bridge/outbox/**/*_dispatch.json"

    inbox_files = list_files(root, inbox_pattern)
    inflight_files = list_files(root, inflight_pattern)
    outbox_files = list_files(root, outbox_pattern)

    checks: Dict[str, Any] = {}
    processor_ok = processor_path.exists()
    checks["task_processor"] = {
        "status": "ok" if processor_ok else "error",
        "path": str(processor_path),
    }
    checks["inbox"] = {
        "status": "ok" if not inbox_files else "warn",
        "count": len(inbox_files),
    }
    checks["inflight"] = {
        "status": "ok" if not inflight_files else "warn",
        "count": len(inflight_files),
    }
    checks["outbox"] = {
        "status": "ok" if not outbox_files else "warn",
        "count": len(outbox_files),
    }

    overall_status = "ok"
    if not processor_ok:
        overall_status = "error"
    elif any(check["status"] == "warn" for check in checks.values()):
        overall_status = "warn"

    payload = {
        "timestamp": now_utc_iso(),
        "overall_status": overall_status,
        "module": "bridge_dispatch_watchdog",
        "checks": checks,
    }
    telemetry_path = root / "observability" / "telemetry" / "bridge_watchdog.latest.json"
    write_json(telemetry_path, payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=int(os.environ.get("BRIDGE_WATCHDOG_INTERVAL", "60")))
    args = ap.parse_args()

    root = Path(args.root or os.environ.get("ROOT", os.path.expanduser("~/0luka"))).resolve()

    if args.loop:
        interval = max(args.interval, 1)
        while True:
            run_once(root)
            time.sleep(interval)
    else:
        run_once(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
