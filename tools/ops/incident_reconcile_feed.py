#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.activity_feed_guard import guarded_append_activity_feed
from tools.ops.audit_feed_chain import _audit


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        raise RuntimeError("runtime_root_missing")
    return Path(raw).expanduser().resolve()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ts_compact() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _write_json(out: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile runtime feed after unhashed-entry incident.")
    parser.add_argument("--json", action="store_true", help="Emit compact JSON")
    args = parser.parse_args()

    try:
        runtime_root = _runtime_root()
    except RuntimeError as exc:
        _write_json({"ok": False, "error": str(exc)}, args.json)
        return 2

    feed_path = runtime_root / "logs" / "activity_feed.jsonl"
    state_path = runtime_root / "state" / "activity_feed_state.json"
    before = _audit(feed_path)
    if before.get("ok"):
        _write_json({"ok": True, "reconciled": False, "message": "already_ok", "before": before}, args.json)
        return 0

    err0 = (before.get("errors") or [{}])[0]
    break_line = int(err0.get("line") or 0)
    if break_line <= 0:
        _write_json({"ok": False, "error": "break_line_unknown", "before": before}, args.json)
        return 2

    stamp = _ts_compact()
    quarantine_dir = runtime_root / "state" / "quarantine" / f"reconcile_{stamp}"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    original = quarantine_dir / "activity_feed.original.jsonl"
    tail = quarantine_dir / "activity_feed.unhashed_tail.jsonl"
    os.replace(feed_path, original)
    if state_path.exists():
        os.replace(state_path, quarantine_dir / "activity_feed_state.original.json")

    with original.open("r", encoding="utf-8") as src, feed_path.open("w", encoding="utf-8") as dst, tail.open("w", encoding="utf-8") as bad:
        for line_no, line in enumerate(src, start=1):
            if line_no < break_line:
                dst.write(line)
            else:
                bad.write(line)

    reanchor_payload = {
        "ts_utc": _utc_now(),
        "ts_epoch_ms": int(time.time_ns() // 1_000_000),
        "phase_id": "LEDGER_INCIDENT_RECOVERY",
        "action": "chain_reanchor",
        "emit_mode": "runtime_auto",
        "verifier_mode": "operational_proof",
        "tool": "incident_reconcile_feed",
        "run_id": f"reanchor_{uuid.uuid4().hex}",
        "status_badge": "PROVEN",
        "detail": {
            "reason": "historical_unhashed_entries",
            "anchor_line": break_line,
            "source_error": err0,
            "quarantine_dir": str(quarantine_dir),
        },
    }
    appended = guarded_append_activity_feed(feed_path, reanchor_payload)
    after = _audit(feed_path)

    result = {
        "ok": bool(appended and after.get("ok")),
        "reconciled": True,
        "appended_reanchor": bool(appended),
        "break_line": break_line,
        "feed_path": str(feed_path),
        "quarantine_dir": str(quarantine_dir),
        "before": before,
        "after": after,
    }
    _write_json(result, args.json)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
