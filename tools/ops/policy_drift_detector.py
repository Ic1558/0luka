#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import approval_state, autonomy_policy

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _approval_state_file(runtime_root: Path) -> Path:
    return runtime_root / "state" / "approval_state.json"


def _approval_actions_file(runtime_root: Path) -> Path:
    return runtime_root / "state" / "approval_actions.jsonl"


def _load_latest_approval_actions(runtime_root: Path) -> dict[str, str]:
    path = _approval_actions_file(runtime_root)
    latest: dict[str, str] = {}
    if not path.exists():
        return latest
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        lane = str(row.get("lane") or "")
        action = str(row.get("action") or "")
        if lane and action in {"approve", "revoke"}:
            latest[lane] = action
    return latest


def _raw_lane_keys(runtime_root: Path) -> set[str]:
    path = _approval_state_file(runtime_root)
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if not isinstance(payload, dict):
        return set()
    return set(payload.keys())


def detect_drift(*, runtime_root: Path | None = None) -> dict[str, Any]:
    resolved_runtime_root = runtime_root or _runtime_root()
    issues: list[dict[str, Any]] = []
    checks = {
        "approval_log_consistency": "OK",
        "expiry_consistency": "OK",
        "env_gate_consistency": "OK",
        "lane_registry_consistency": "OK",
    }

    state = approval_state.load_approval_state(runtime_root=resolved_runtime_root)
    policy = autonomy_policy.evaluate_policy(runtime_root=resolved_runtime_root)
    latest_actions = _load_latest_approval_actions(resolved_runtime_root)

    for lane in approval_state.LANES:
        lane_state = state["lanes"][lane]
        lane_policy = policy.get("lanes", {}).get(lane, {})

        # 1) approval log consistency
        last_action = latest_actions.get(lane)
        if last_action == "revoke" and bool(lane_state.get("approved")):
            checks["approval_log_consistency"] = "DRIFT"
            issues.append(
                {
                    "type": "approval_log_drift",
                    "lane": lane,
                    "details": "state approved but last log action is revoke",
                }
            )
        if last_action == "approve" and not bool(lane_state.get("approved")):
            checks["approval_log_consistency"] = "DRIFT"
            issues.append(
                {
                    "type": "approval_log_drift",
                    "lane": lane,
                    "details": "state revoked but last log action is approve",
                }
            )

        # 2) expiry consistency
        if bool(lane_state.get("approved")) and bool(lane_state.get("expired")):
            checks["expiry_consistency"] = "DRIFT"
            issues.append(
                {
                    "type": "expiry_drift",
                    "lane": lane,
                    "details": "approval expired but still active",
                }
            )

        # 3) env gate consistency
        if lane_policy.get("status") == "allowed" and not bool(lane_policy.get("env_gate_present")):
            checks["env_gate_consistency"] = "DRIFT"
            issues.append(
                {
                    "type": "env_gate_drift",
                    "lane": lane,
                    "details": "status allowed while env gate missing",
                }
            )

    # 4) lane registry consistency
    known = set(approval_state.LANES)
    for unknown in sorted(_raw_lane_keys(resolved_runtime_root) - known):
        checks["lane_registry_consistency"] = "DRIFT"
        issues.append(
            {
                "type": "lane_registry_drift",
                "lane": unknown,
                "details": "unknown lane in approval_state",
            }
        )

    return {
        "ok": len(issues) == 0,
        "drift_count": len(issues),
        "checks": checks,
        "issues": issues,
        "runtime_root": str(resolved_runtime_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect policy drift against governance consistency checks.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = detect_drift()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
