#!/usr/bin/env python3
"""Alert Storm Guard v1.1 — contract-compliant dedup

Dedup key: (workflow_name, check_name, branch)

State schema per key:
  last_failure_ts      - epoch float of last failure event
  last_success_ts      - epoch float of last success event (None if none)
  last_alert_ts        - epoch float of last alert sent (None if no alert yet)
  last_alert_severity  - "CRITICAL" | "WARNING" | None
  last_event_type      - "fail" | "success"
  last_event_run_id    - str, GitHub run ID for trace

Decision tree for --mode fail (checked in order):
  1. suppress_newer_success   — last_success_ts >= event_ts
  2. suppress_duplicate_window — now - last_alert_ts < WINDOW_SEC
  3. emit_alert               — record state and emit

For --mode success:
  - Update last_success_ts only. No alert. Exit 0.

Exit code: 0 = emit_alert or success_state_updated, 1 = suppressed
Output: single JSON line to stdout with decision, severity, reason
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WINDOW_SEC = 3600    # 60-minute dedup window
TTL_SEC = 86400      # 24h — purge entries older than this

# Severity mapping: workflow display name → severity
CRITICAL_WORKFLOWS = frozenset([
    "tier2-integrity",
    "ci / retention-smoke",
])

_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_PATH = _ROOT / "observability" / "telemetry" / "alert_dedup_state.json"


def get_severity(workflow: str) -> str:
    return "CRITICAL" if workflow in CRITICAL_WORKFLOWS else "WARNING"


def _parse_ts(ts_str: str) -> float:
    """Parse ISO-8601 UTC string to epoch float."""
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()


def _now_from_arg(now_ts_utc: str | None) -> float:
    if now_ts_utc:
        return _parse_ts(now_ts_utc)
    return time.time()


def _dedup_key(workflow: str, check_name: str, branch: str) -> str:
    return f"{workflow}|{check_name}|{branch}"


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state_atomic(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _clean_state(state: dict, now: float) -> dict:
    """Remove entries where all timestamps are older than TTL_SEC."""
    out = {}
    for k, v in state.items():
        latest = max(
            v.get("last_failure_ts") or 0.0,
            v.get("last_success_ts") or 0.0,
            v.get("last_alert_ts") or 0.0,
        )
        if now - latest < TTL_SEC:
            out[k] = v
    return out


def handle_fail(workflow: str, check_name: str, branch: str, run_id: str,
                event_ts: float, now: float, state_path: Path) -> dict:
    """Process a failure event. Returns result dict. Saves state."""
    severity = get_severity(workflow)
    key = _dedup_key(workflow, check_name, branch)
    state = _load_state(state_path)
    state = _clean_state(state, now)
    entry = state.get(key, {})

    # 1. suppress_newer_success: recorded success is >= this failure's timestamp
    last_success_ts = entry.get("last_success_ts")
    if last_success_ts is not None and last_success_ts >= event_ts:
        entry.update({
            "last_failure_ts": event_ts,
            "last_event_type": "fail",
            "last_event_run_id": run_id,
        })
        state[key] = entry
        _save_state_atomic(state_path, state)
        return {
            "decision": "suppress_newer_success",
            "severity": severity,
            "reason": (
                f"last_success_ts={last_success_ts:.0f} >= event_ts={event_ts:.0f}"
            ),
        }

    # 2. suppress_duplicate_window: alerted within WINDOW_SEC
    last_alert_ts = entry.get("last_alert_ts")
    if last_alert_ts is not None:
        age = now - last_alert_ts
        if age < WINDOW_SEC:
            entry.update({
                "last_failure_ts": event_ts,
                "last_event_type": "fail",
                "last_event_run_id": run_id,
            })
            state[key] = entry
            _save_state_atomic(state_path, state)
            return {
                "decision": "suppress_duplicate_window",
                "severity": severity,
                "reason": f"last_alert_age={age:.0f}s < {WINDOW_SEC}s",
            }

    # 3. emit_alert
    entry.update({
        "last_failure_ts": event_ts,
        "last_alert_ts": now,
        "last_alert_severity": severity,
        "last_event_type": "fail",
        "last_event_run_id": run_id,
    })
    state[key] = entry
    _save_state_atomic(state_path, state)
    return {
        "decision": "emit_alert",
        "severity": severity,
        "reason": "first_failure_in_window",
    }


def handle_success(workflow: str, check_name: str, branch: str, run_id: str,
                   event_ts: float, now: float, state_path: Path) -> dict:
    """Process a success event. Updates last_success_ts only. No alert."""
    key = _dedup_key(workflow, check_name, branch)
    state = _load_state(state_path)
    state = _clean_state(state, now)
    entry = state.get(key, {})
    entry.update({
        "last_success_ts": event_ts,
        "last_event_type": "success",
        "last_event_run_id": run_id,
    })
    state[key] = entry
    _save_state_atomic(state_path, state)
    return {
        "decision": "success_state_updated",
        "reason": f"last_success_ts={event_ts:.0f}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Alert Storm Guard v1.1")
    parser.add_argument("--mode", choices=["fail", "success"], required=True,
                        help="Event type")
    parser.add_argument("--workflow", required=True, help="Workflow display name")
    parser.add_argument("--branch", required=True, help="Head branch")
    parser.add_argument("--check-name", required=True, dest="check_name",
                        help="Failing/passing check/job name")
    parser.add_argument("--run-id", required=True, help="GitHub run ID")
    parser.add_argument("--event-ts-utc", default=None,
                        help="ISO-8601 UTC timestamp of the event (default: now)")
    parser.add_argument("--now-ts-utc", default=None,
                        help="Override for 'now' — for deterministic replay testing")
    parser.add_argument("--state-path", default=str(STATE_PATH),
                        help="Path to dedup state JSON")
    args = parser.parse_args()

    now = _now_from_arg(args.now_ts_utc)
    event_ts = _parse_ts(args.event_ts_utc) if args.event_ts_utc else now
    state_path = Path(args.state_path)

    if args.mode == "success":
        result = handle_success(
            workflow=args.workflow,
            check_name=args.check_name,
            branch=args.branch,
            run_id=args.run_id,
            event_ts=event_ts,
            now=now,
            state_path=state_path,
        )
        print(json.dumps(result))
        sys.exit(0)
    else:
        result = handle_fail(
            workflow=args.workflow,
            check_name=args.check_name,
            branch=args.branch,
            run_id=args.run_id,
            event_ts=event_ts,
            now=now,
            state_path=state_path,
        )
        print(json.dumps(result))
        sys.exit(0 if result["decision"] == "emit_alert" else 1)


if __name__ == "__main__":
    main()
