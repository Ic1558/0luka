#!/usr/bin/env python3
"""Alert Storm Guard v1 — dedup logic for luka_ai_failure_alert.yml

Decision tree (checked in order):
  1. suppress_newer_success  — a newer successful run exists (caller sets --newer-success flag)
  2. suppress_duplicate_window — same (workflow, branch) alerted within WINDOW_SEC
  3. emit_alert               — no suppression; record state and emit

Exit code: 0 = emit alert, 1 = suppress
State file: observability/telemetry/alert_dedup_state.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

WINDOW_SEC = 3600    # 60-minute dedup window
TTL_SEC = 86400      # 24h — clean entries older than this on every write

_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_PATH = _ROOT / "observability" / "telemetry" / "alert_dedup_state.json"


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
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
    """Remove entries older than TTL_SEC."""
    return {k: v for k, v in state.items() if now - v.get("ts", 0) < TTL_SEC}


def _dedup_key(workflow: str, branch: str) -> str:
    return f"{workflow}|{branch}"


def check_and_record(workflow: str, branch: str, run_id: str, newer_success: bool,
                     state_path: Path) -> str:
    """
    Returns decision string and records state if emitting.
    Caller checks return value:
      suppress_newer_success  → exit 1
      suppress_duplicate_window:<age>s → exit 1
      emit_alert              → exit 0
    """
    now = time.time()
    state = _load_state(state_path)
    state = _clean_state(state, now)

    # Check 1: newer success passed in from GitHub API check
    if newer_success:
        return "suppress_newer_success"

    # Check 2: duplicate within window
    key = _dedup_key(workflow, branch)
    if key in state:
        age = now - state[key].get("ts", 0)
        if age < WINDOW_SEC:
            return f"suppress_duplicate_window:{age:.0f}s"

    # Emit: record state
    state[key] = {
        "ts": now,
        "run_id": run_id,
        "workflow": workflow,
        "branch": branch,
    }
    _save_state_atomic(state_path, state)
    return "emit_alert"


def main() -> None:
    parser = argparse.ArgumentParser(description="Alert Storm Guard v1 dedup check")
    parser.add_argument("--workflow", required=True, help="Workflow display name")
    parser.add_argument("--branch", required=True, help="Head branch")
    parser.add_argument("--run-id", required=True, help="GitHub run ID")
    parser.add_argument("--newer-success", action="store_true",
                        help="Caller confirmed a newer successful run exists; suppress")
    parser.add_argument("--state-path", default=str(STATE_PATH),
                        help="Path to dedup state JSON (default: observability/telemetry/alert_dedup_state.json)")
    args = parser.parse_args()

    decision = check_and_record(
        workflow=args.workflow,
        branch=args.branch,
        run_id=args.run_id,
        newer_success=args.newer_success,
        state_path=Path(args.state_path),
    )

    print(decision)
    sys.exit(0 if decision == "emit_alert" else 1)


if __name__ == "__main__":
    main()
