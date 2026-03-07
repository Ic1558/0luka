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

from tools.ops import memory_recovery, worker_recovery

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
API_RESTART_PATH = ROOT / "core_brain" / "ops" / "governance" / "handlers" / "service_restart.zsh"


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


def _approval_present(flag_name: str) -> bool:
    return os.environ.get(flag_name, "").strip() == "1"


def _run_api_restart() -> tuple[bool, str]:
    if not API_RESTART_PATH.exists():
        return False, f"restart_path_missing:{API_RESTART_PATH}"
    proc = subprocess.run(
        ["/bin/zsh", str(API_RESTART_PATH)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return True, "api_restart_executed"
    detail = proc.stderr.strip() or proc.stdout.strip() or f"returncode={proc.returncode}"
    return False, f"api_restart_failed:{detail}"


def evaluate_remediation(
    runtime_status: dict[str, Any],
    operator_status: dict[str, Any],
    *,
    timestamp: str | None = None,
) -> list[dict[str, Any]]:
    ts = timestamp or _utc_now()
    decisions: list[dict[str, Any]] = []

    runtime_overall = str(runtime_status.get("overall_status", "FAILED")).upper()
    operator_overall = str(operator_status.get("overall_status", "CRITICAL")).upper()
    api_status = str(operator_status.get("api_server", "MISSING")).upper()
    redis_status = str(operator_status.get("redis", "MISSING")).upper()
    memory_status = str(operator_status.get("memory_status", "UNAVAILABLE")).upper()

    if api_status == "MISSING":
        if not _approval_present("LUKA_ALLOW_API_RESTART"):
            decisions.append(
                _decision(
                    timestamp=ts,
                    decision="approval_missing",
                    target="api",
                    reason="api_server=MISSING; approval_missing:LUKA_ALLOW_API_RESTART",
                    action_taken=False,
                )
            )
        elif not API_RESTART_PATH.exists():
            decisions.append(
                _decision(
                    timestamp=ts,
                    decision="action_unavailable",
                    target="api",
                    reason=f"api_server=MISSING; restart_path_missing:{API_RESTART_PATH}",
                    action_taken=False,
                )
            )
        else:
            ok, reason = _run_api_restart()
            decisions.append(
                _decision(
                    timestamp=ts,
                    decision="restart_api",
                    target="api",
                    reason=f"api_server=MISSING; {reason}",
                    action_taken=ok,
                )
            )

    if redis_status == "MISSING":
        if not _approval_present("LUKA_ALLOW_REDIS_RESTART"):
            decisions.append(
                _decision(
                    timestamp=ts,
                    decision="approval_missing",
                    target="redis",
                    reason="redis=MISSING; approval_missing:LUKA_ALLOW_REDIS_RESTART",
                    action_taken=False,
                )
            )
        else:
            decisions.append(
                _decision(
                    timestamp=ts,
                    decision="action_unavailable",
                    target="redis",
                    reason="redis=MISSING; no_safe_restart_path_configured",
                    action_taken=False,
                )
            )

    if memory_status == "CRITICAL":
        decisions.extend(memory_recovery.evaluate_memory_recovery(runtime_status, operator_status, timestamp=ts))

    bridge_needs_recovery, _ = worker_recovery.bridge_recovery_required(operator_status)
    if bridge_needs_recovery:
        decisions.extend(worker_recovery.evaluate_worker_recovery(runtime_status, operator_status, timestamp=ts))

    if decisions:
        return decisions

    return [
        _decision(
            timestamp=ts,
            decision="noop",
            target="none",
            reason=f"runtime={runtime_overall}; operator={operator_overall}; no_remediation_required",
            action_taken=False,
        )
    ]


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
    decisions = evaluate_remediation(runtime_status, operator_status)
    append_decisions(_remediation_log_path(resolved_runtime_root), decisions)
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one remediation decision cycle.")
    parser.add_argument("--once", action="store_true", help="Run one remediation cycle")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    if not args.once:
        parser.error("--once is required in Phase 5.1")

    try:
        decisions = run_once()
    except Exception as exc:
        payload = {"ok": False, "errors": [f"remediation_engine_failed:{exc}"]}
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
