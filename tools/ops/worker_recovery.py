#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
SAFE_WORKER_RECOVERY_PATH = ROOT / "tools" / "ops" / "worker_recovery_safe.zsh"
_OK_CONSUMER_STATES = {"idle", "ok", "running"}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _remediation_log_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "remediation_actions.jsonl"


def _run_json_command(args: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    stream = proc.stdout.strip() or proc.stderr.strip()
    if not stream:
        raise RuntimeError(f"empty_output:{' '.join(args)}")
    payload = json.loads(stream)
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{' '.join(args)}")
    payload["_returncode"] = proc.returncode
    return payload


def load_runtime_status(*, runtime_root: Path | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["LUKA_RUNTIME_ROOT"] = str(runtime_root or _runtime_root())
    return _run_json_command([sys.executable, "tools/ops/runtime_status_report.py", "--json"], env=env)


def load_operator_status(*, runtime_root: Path | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["LUKA_RUNTIME_ROOT"] = str(runtime_root or _runtime_root())
    return _run_json_command([sys.executable, "tools/ops/operator_status_report.py", "--json"], env=env)


def _decision(*, timestamp: str, decision: str, target: str, reason: str, action_taken: bool) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "decision": decision,
        "target": target,
        "reason": reason,
        "action_taken": action_taken,
        "source": "remediation_engine",
    }


def _approval_present() -> bool:
    return os.environ.get("LUKA_ALLOW_WORKER_RECOVERY", "").strip() == "1"


def _recovery_action_available() -> bool:
    return SAFE_WORKER_RECOVERY_PATH.exists()


def _run_recovery_action() -> tuple[bool, str]:
    proc = subprocess.run(
        ["/bin/zsh", str(SAFE_WORKER_RECOVERY_PATH)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return True, "worker_recovery_completed"
    detail = proc.stderr.strip() or proc.stdout.strip() or f"returncode={proc.returncode}"
    return False, f"worker_recovery_failed:{detail}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def bridge_recovery_required(operator_status: dict[str, Any]) -> tuple[bool, str]:
    bridge_status = str(operator_status.get("bridge_status", "UNAVAILABLE")).upper()
    details = operator_status.get("details") if isinstance(operator_status.get("details"), dict) else {}
    bridge_checks = details.get("bridge_checks") if isinstance(details.get("bridge_checks"), dict) else {}
    errors = operator_status.get("errors") if isinstance(operator_status.get("errors"), list) else []
    consumer_payload = details.get("bridge_consumer") if isinstance(details.get("bridge_consumer"), dict) else None
    watchdog_payload = details.get("bridge_watchdog") if isinstance(details.get("bridge_watchdog"), dict) else None

    reasons: list[str] = []
    if bridge_status != "OK":
        reasons.append(f"bridge_status={bridge_status}")

    if consumer_payload is None:
        reasons.append("bridge_consumer=missing_or_invalid")
    if watchdog_payload is None:
        reasons.append("bridge_watchdog=missing_or_invalid")

    consumer_status = str(bridge_checks.get("consumer", "unavailable")).lower()
    inflight_status = str(bridge_checks.get("inflight", "unavailable")).lower()
    outbox_status = str(bridge_checks.get("outbox", "unavailable")).lower()

    if consumer_status not in _OK_CONSUMER_STATES:
        reasons.append(f"consumer={consumer_status}")
    if inflight_status != "ok":
        reasons.append(f"inflight={inflight_status}")
    if outbox_status != "ok":
        reasons.append(f"outbox={outbox_status}")

    for item in errors:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        error = str(item.get("error", "unknown_error"))
        if "bridge_consumer" in path or "bridge_watchdog" in path:
            reasons.append(f"{error}:{Path(path).name}")

    unique = _dedupe(reasons)
    if unique:
        return True, "; ".join(unique)
    return False, "bridge_status=OK"


def evaluate_worker_recovery(
    runtime_status: dict[str, Any],
    operator_status: dict[str, Any],
    *,
    timestamp: str | None = None,
) -> list[dict[str, Any]]:
    ts = timestamp or _utc_now()
    runtime_overall = str(runtime_status.get("overall_status", "FAILED")).upper()
    operator_overall = str(operator_status.get("overall_status", "CRITICAL")).upper()
    needs_recovery, reason = bridge_recovery_required(operator_status)

    if not needs_recovery:
        return [
            _decision(
                timestamp=ts,
                decision="noop",
                target="none",
                reason=f"runtime={runtime_overall}; operator={operator_overall}; bridge_status=OK",
                action_taken=False,
            )
        ]

    if not _approval_present():
        return [
            _decision(
                timestamp=ts,
                decision="approval_missing",
                target="bridge",
                reason=f"{reason}; approval_missing:LUKA_ALLOW_WORKER_RECOVERY",
                action_taken=False,
            )
        ]

    if not _recovery_action_available():
        return [
            _decision(
                timestamp=ts,
                decision="action_unavailable",
                target="bridge",
                reason=f"{reason}; recovery_path_missing:{SAFE_WORKER_RECOVERY_PATH}",
                action_taken=False,
            )
        ]

    started = _decision(
        timestamp=ts,
        decision="worker_recovery_started",
        target="worker",
        reason=f"{reason}; recovery_path={SAFE_WORKER_RECOVERY_PATH}",
        action_taken=True,
    )
    ok, detail = _run_recovery_action()
    finished = _decision(
        timestamp=ts,
        decision="worker_recovery_finished",
        target="worker",
        reason=detail,
        action_taken=ok,
    )
    return [started, finished]


def append_decisions(log_path: Path, decisions: list[dict[str, Any]]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_once(*, runtime_root: Path | None = None) -> list[dict[str, Any]]:
    resolved_runtime_root = runtime_root or _runtime_root()
    runtime_status = load_runtime_status(runtime_root=resolved_runtime_root)
    operator_status = load_operator_status(runtime_root=resolved_runtime_root)
    decisions = evaluate_worker_recovery(runtime_status, operator_status)
    append_decisions(_remediation_log_path(resolved_runtime_root), decisions)
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded bridge/worker recovery decision path once.")
    parser.add_argument("--once", action="store_true", help="Run one worker recovery decision cycle")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    if not args.once:
        parser.error("--once is required in Phase 5.4")

    try:
        decisions = run_once()
    except Exception as exc:
        payload = {"ok": False, "errors": [f"worker_recovery_failed:{exc}"]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"ok": True, "decisions": decisions}, ensure_ascii=False))
    else:
        for decision in decisions:
            print(json.dumps(decision, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
