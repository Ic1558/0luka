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
POLICY_MEMORY_NAME = "policy_memory.json"
MEMORY_INDEX_METADATA_NAME = "memory_index_metadata.json"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _remediation_log_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "remediation_actions.jsonl"


def _state_dir(runtime_root: Path) -> Path:
    return runtime_root / "state"


def _policy_memory_path(runtime_root: Path) -> Path:
    return _state_dir(runtime_root) / POLICY_MEMORY_NAME


def _memory_index_metadata_path(runtime_root: Path) -> Path:
    return _state_dir(runtime_root) / MEMORY_INDEX_METADATA_NAME


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
    return os.environ.get("LUKA_ALLOW_MEMORY_RECOVERY", "").strip() == "1"


def _load_policy_memory(runtime_root: Path) -> dict[str, Any]:
    payload = json.loads(_policy_memory_path(runtime_root).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("policy_memory_not_object")
    return payload


def _recovery_action_available(runtime_root: Path) -> tuple[bool, str]:
    state_dir = _state_dir(runtime_root)
    if not state_dir.is_dir():
        return False, f"state_dir_missing:{state_dir}"
    policy_path = _policy_memory_path(runtime_root)
    if not policy_path.is_file():
        return False, f"policy_memory_missing:{policy_path}"
    output_path = _memory_index_metadata_path(runtime_root)
    if output_path.parent != state_dir or output_path.name != MEMORY_INDEX_METADATA_NAME:
        return False, f"unsafe_output_path:{output_path}"
    return True, f"memory_index_metadata:{output_path}"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _run_recovery_action(runtime_root: Path, runtime_status: dict[str, Any], operator_status: dict[str, Any], *, timestamp: str) -> tuple[bool, str]:
    try:
        policy_memory = _load_policy_memory(runtime_root)
    except Exception as exc:
        return False, f"memory_recovery_failed:{exc}"

    protected_domains = policy_memory.get("protected_domains")
    outcomes = policy_memory.get("outcomes")
    metadata = {
        "schema_version": 1,
        "rebuilt_at": timestamp,
        "runtime_status": str(runtime_status.get("overall_status", "FAILED")).upper(),
        "operator_status": str(operator_status.get("overall_status", "CRITICAL")).upper(),
        "memory_status": str(operator_status.get("memory_status", "UNAVAILABLE")).upper(),
        "policy_memory_updated_at": policy_memory.get("updated_at"),
        "protected_domain_count": len(protected_domains) if isinstance(protected_domains, list) else 0,
        "outcome_count": len(outcomes) if isinstance(outcomes, list) else 0,
        "source": "memory_recovery",
    }
    try:
        _write_json_atomic(_memory_index_metadata_path(runtime_root), metadata)
    except Exception as exc:
        return False, f"memory_recovery_failed:{exc}"
    return True, f"memory_index_metadata_rebuilt:{_memory_index_metadata_path(runtime_root)}"


def evaluate_memory_recovery(
    runtime_status: dict[str, Any],
    operator_status: dict[str, Any],
    *,
    timestamp: str | None = None,
    runtime_root: Path | None = None,
) -> list[dict[str, Any]]:
    ts = timestamp or _utc_now()
    resolved_runtime_root = runtime_root or _runtime_root()
    runtime_overall = str(runtime_status.get("overall_status", "FAILED")).upper()
    operator_overall = str(operator_status.get("overall_status", "CRITICAL")).upper()
    memory_status = str(operator_status.get("memory_status", "UNAVAILABLE")).upper()

    if memory_status != "CRITICAL":
        return [
            _decision(
                timestamp=ts,
                decision="noop",
                target="none",
                reason=f"runtime={runtime_overall}; operator={operator_overall}; memory_status={memory_status}",
                action_taken=False,
            )
        ]

    if not _approval_present():
        return [
            _decision(
                timestamp=ts,
                decision="approval_missing",
                target="memory",
                reason="memory_status=CRITICAL; approval_missing:LUKA_ALLOW_MEMORY_RECOVERY",
                action_taken=False,
            )
        ]

    action_available, action_detail = _recovery_action_available(resolved_runtime_root)
    if not action_available:
        return [
            _decision(
                timestamp=ts,
                decision="action_unavailable",
                target="memory",
                reason=f"memory_status=CRITICAL; {action_detail}",
                action_taken=False,
            )
        ]

    started = _decision(
        timestamp=ts,
        decision="memory_recovery_started",
        target="memory",
        reason=f"memory_status=CRITICAL; {action_detail}",
        action_taken=True,
    )
    ok, detail = _run_recovery_action(resolved_runtime_root, runtime_status, operator_status, timestamp=ts)
    finished = _decision(
        timestamp=ts,
        decision="memory_recovery_finished",
        target="memory",
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
    decisions = evaluate_memory_recovery(runtime_status, operator_status, runtime_root=resolved_runtime_root)
    append_decisions(_remediation_log_path(resolved_runtime_root), decisions)
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded memory recovery decision path once.")
    parser.add_argument("--once", action="store_true", help="Run one memory recovery decision cycle")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    if not args.once:
        parser.error("--once is required in Phase 5.3")

    try:
        decisions = run_once()
    except Exception as exc:
        payload = {"ok": False, "errors": [f"memory_recovery_failed:{exc}"]}
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
