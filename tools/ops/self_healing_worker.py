#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import autonomy_policy, recovery_guardrails, remediation_queue

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
ACTION_LANE = {
    "restart_worker": "worker_recovery",
    "restart_api": "api_recovery",
    "redis_reconnect": "redis_recovery",
}
ACTION_ENV_CMD = {
    "restart_worker": "LUKA_SELF_HEALING_CMD_RESTART_WORKER",
    "restart_api": "LUKA_SELF_HEALING_CMD_RESTART_API",
    "redis_reconnect": "LUKA_SELF_HEALING_CMD_REDIS_RECONNECT",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _history_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "remediation_history.jsonl"


def _append_history(
    *,
    runtime_root: Path,
    queue_id: str,
    lane: str,
    action: str,
    result: str,
    attempt: int,
    decision: str | None = None,
    reason: str | None = None,
) -> None:
    entry = {
        "timestamp": _utc_now(),
        "queue_id": queue_id,
        "lane": lane,
        "action": action,
        "result": result,
        "attempt": attempt,
    }
    if decision:
        entry["decision"] = decision
    if reason:
        entry["reason"] = reason
    path = _history_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _first_queued_item(runtime_root: Path) -> dict[str, Any] | None:
    payload = remediation_queue.list_queue(runtime_root=runtime_root)
    rows = payload.get("items")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("state") == "queued":
            return row
    return None


def _policy_allows(*, runtime_root: Path, lane: str) -> tuple[bool, str]:
    payload = autonomy_policy.evaluate_policy(runtime_root=runtime_root, lane=lane)
    lane_payload = payload.get("lanes", {}).get(lane, {})
    if not isinstance(lane_payload, dict):
        return False, "lane_policy_missing"
    status = str(lane_payload.get("status") or "denied")
    reason = str(lane_payload.get("reason") or "policy_denied")
    return status == "allowed", reason


def _resolve_action_cmd(action: str) -> list[str]:
    env_key = ACTION_ENV_CMD.get(action)
    if env_key:
        raw = os.environ.get(env_key, "").strip()
        if raw:
            return shlex.split(raw)
    if action == "restart_worker":
        return [sys.executable, "tools/ops/worker_recovery.py", "--once", "--json"]
    if action == "restart_api":
        return [sys.executable, "tools/ops/remediation_engine.py", "--once", "--json"]
    if action == "redis_reconnect":
        return [sys.executable, "tools/ops/remediation_engine.py", "--once", "--json"]
    raise RuntimeError(f"unsupported_action:{action}")


def _execute_action(action: str) -> tuple[bool, str]:
    cmd = _resolve_action_cmd(action)
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    output = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0:
        return False, output or f"exit_code:{proc.returncode}"
    return True, output


def process_once(*, runtime_root: Path | None = None) -> dict[str, Any]:
    resolved_runtime_root = runtime_root or _runtime_root()
    item = _first_queued_item(resolved_runtime_root)
    if not item:
        return {"ok": True, "processed": False, "reason": "no_queued_items"}

    queue_id = str(item.get("id") or "")
    action = str(item.get("action") or "")
    lane = str(item.get("lane") or ACTION_LANE.get(action, ""))
    attempts = int(item.get("attempts", 0))

    if not queue_id or not lane:
        raise RuntimeError("queue_item_invalid")

    allowed, policy_reason = _policy_allows(runtime_root=resolved_runtime_root, lane=lane)
    if not allowed:
        transition = remediation_queue.transition_item(
            item_id=queue_id,
            state="blocked",
            attempts=attempts,
            runtime_root=resolved_runtime_root,
        )
        _append_history(
            runtime_root=resolved_runtime_root,
            queue_id=queue_id,
            lane=lane,
            action=action,
            result="blocked",
            attempt=int(transition["item"].get("attempts", attempts)),
            decision="policy_denied",
            reason=policy_reason,
        )
        return {
            "ok": True,
            "processed": True,
            "queue_id": queue_id,
            "lane": lane,
            "action": action,
            "result": "blocked",
            "reason": policy_reason,
        }

    guardrail = recovery_guardrails.evaluate(
        lane=lane,
        action=action,
        item_attempts=attempts,
        runtime_root=resolved_runtime_root,
    )
    if not bool(guardrail.get("allowed")):
        next_state = str(guardrail.get("queue_state") or "blocked")
        transition = remediation_queue.transition_item(
            item_id=queue_id,
            state=next_state,
            attempts=attempts,
            runtime_root=resolved_runtime_root,
        )
        _append_history(
            runtime_root=resolved_runtime_root,
            queue_id=queue_id,
            lane=lane,
            action=action,
            result=next_state,
            attempt=int(transition["item"].get("attempts", attempts)),
            decision=str(guardrail.get("decision") or "guardrail_denied"),
        )
        return {
            "ok": True,
            "processed": True,
            "queue_id": queue_id,
            "lane": lane,
            "action": action,
            "result": next_state,
            "reason": str(guardrail.get("decision") or "guardrail_denied"),
        }

    running = remediation_queue.transition_item(
        item_id=queue_id,
        state="running",
        runtime_root=resolved_runtime_root,
    )
    run_attempt = int(running["item"].get("attempts", attempts))
    success, details = _execute_action(action)

    final_state = "success" if success else "failed"
    remediation_queue.transition_item(
        item_id=queue_id,
        state=final_state,
        attempts=run_attempt,
        runtime_root=resolved_runtime_root,
    )
    guardrail_record = recovery_guardrails.register_result(
        lane=lane,
        action=action,
        result=final_state,
        runtime_root=resolved_runtime_root,
    )
    _append_history(
        runtime_root=resolved_runtime_root,
        queue_id=queue_id,
        lane=lane,
        action=action,
        result=final_state,
        attempt=run_attempt,
        decision=str(guardrail_record.get("decision") or "executed"),
    )
    return {
        "ok": True,
        "processed": True,
        "queue_id": queue_id,
        "lane": lane,
        "action": action,
        "result": final_state,
        "attempt": run_attempt,
        "details": details,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="0luka self-healing runtime worker")
    parser.add_argument("--once", action="store_true", help="process one queue item and exit")
    parser.add_argument("--loop", action="store_true", help="run loop mode")
    parser.add_argument("--interval", type=int, default=5, help="loop interval seconds")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    loop_mode = args.loop and not args.once
    interval = max(1, int(args.interval))

    if loop_mode:
        try:
            while True:
                payload = process_once()
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                time.sleep(interval)
        except KeyboardInterrupt:
            return 0
        return 0

    payload = process_once()
    if args.json or True:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
