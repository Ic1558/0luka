#!/usr/bin/env python3
"""
System Health Endpoint v1 -- single command to check 0luka system state.

Usage:
    python3 core/health.py               # quick check
    python3 core/health.py --full        # include test suite run
    python3 core/health.py --json        # machine-readable
"""
from __future__ import annotations

import json
import hashlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from core.config import (
        COMPLETED,
        DISPATCH_LATEST as DISPATCH_LATEST_PATH,
        DISPATCH_HEARTBEAT,
        INBOX,
        OUTBOX_TASKS,
        REJECTED,
        ROOT,
        SCHEMA_REGISTRY,
        VERIFY_DIR,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import (
        COMPLETED,
        DISPATCH_LATEST as DISPATCH_LATEST_PATH,
        DISPATCH_HEARTBEAT,
        INBOX,
        OUTBOX_TASKS,
        REJECTED,
        ROOT,
        SCHEMA_REGISTRY,
        VERIFY_DIR,
    )

from core.result_reader import (
    detect_result_authority_mismatches,
    get_envelope_seal_verified,
    get_result_execution_events,
    get_result_provenance_hashes,
    get_result_status,
    get_result_summary,
)

HEARTBEAT = DISPATCH_HEARTBEAT
DISPATCH_LATEST = DISPATCH_LATEST_PATH
OUTBOX = OUTBOX_TASKS
SCHEMA_PATH = SCHEMA_REGISTRY
CACHE_PATH = ROOT / "observability" / "artifacts" / "health_latest.json"

TEST_SUITES = [
    "test_ref_resolver.py",
    "test_phase1c_gate.py",
    "test_phase1d_result_gate.py",
    "test_phase1e_outbox_writer.py",
    "test_phase1e_no_hardpath_in_result.py",
    "test_clec_gate.py",
    "test_e2e_clec_pipeline.py",
    "test_task_dispatcher.py",
    "test_submit.py",
    "test_health.py",
    "test_smoke.py",
    "test_ledger.py",
    "test_retention.py",
    "test_config.py",
    "test_cli.py",
    "test_bridge.py",
    "test_timeline.py",
    "test_seal.py",
    "test_circuit_breaker.py",
    "test_watchdog.py",
    "test_pack10_index_sovereignty.py",
]

ENV_CONFIG_PATH = ROOT / "core" / "contracts" / "v1" / "0luka_schemas.json"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    """Read JSON file, return None if missing/invalid."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def _run_cmd(args: List[str], *, cwd: Path, timeout: float) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
        )
        if proc.returncode != 0:
            return False, ""
        return True, (proc.stdout or "").strip()
    except Exception:
        return False, ""


def _probe_env() -> Dict[str, Any]:
    # Git probe (fail-closed)
    ok_branch, branch = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, timeout=2)
    ok_head, head_sha = _run_cmd(["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=2)
    ok_porcelain, porcelain = _run_cmd(["git", "status", "--porcelain"], cwd=ROOT, timeout=2)
    if not (ok_branch and ok_head and ok_porcelain):
        git_env = {
            "branch": "unknown",
            "head_sha": "unknown",
            "dirty": True,
            "uncommitted_count": -1,
        }
    else:
        lines = [line for line in porcelain.splitlines() if line.strip()]
        git_env = {
            "branch": branch or "unknown",
            "head_sha": head_sha or "unknown",
            "dirty": len(lines) > 0,
            "uncommitted_count": len(lines),
        }

    # launchd probe (fail-closed)
    services = {
        "com.0luka.heartbeat": "inactive",
        "com.0luka.librarian_apply": "inactive",
        "com.0luka.inbox_bridge": "inactive",
    }
    ok_launchctl, launchctl_out = _run_cmd(["launchctl", "list"], cwd=ROOT, timeout=2)
    if ok_launchctl and launchctl_out:
        for name in list(services.keys()):
            if name in launchctl_out:
                services[name] = "active"

    # service probe (Mission Control) (fail-closed)
    alive = False
    try:
        with socket.create_connection(("127.0.0.1", 7010), timeout=0.5):
            alive = True
    except Exception:
        alive = False

    # config hash (fail-closed)
    if not ENV_CONFIG_PATH.exists():
        config_hash = "missing"
    else:
        try:
            config_hash = hashlib.sha256(ENV_CONFIG_PATH.read_bytes()).hexdigest()
        except Exception:
            config_hash = "missing"

    return {
        "git": git_env,
        "launchd": {
            "heartbeat": services["com.0luka.heartbeat"],
            "librarian_apply": services["com.0luka.librarian_apply"],
            "inbox_bridge": services["com.0luka.inbox_bridge"],
        },
        "services": {
            "mission_control": {
                "port": 7010,
                "alive": bool(alive),
            }
        },
        "config_hash": config_hash,
    }


def _count_files(directory: Path, pattern: str = "*") -> int:
    """Count files matching pattern in directory."""
    if not directory.exists():
        return 0
    return sum(1 for f in directory.glob(pattern) if f.is_file())


def _count_inbox() -> int:
    """Count pending task files in inbox (top-level task_*.yaml only)."""
    if not INBOX.exists():
        return 0
    return sum(1 for f in INBOX.glob("task_*.yaml") if f.is_file())


def _get_schemas() -> List[str]:
    """Get list of registered schema names."""
    data = _read_json(SCHEMA_PATH)
    if not data:
        return []
    return sorted(data.get("$defs", {}).keys())


def _check_dispatcher() -> Dict[str, Any]:
    """Check dispatcher heartbeat status."""
    hb = _read_json(HEARTBEAT)
    if not hb:
        return {"status": "not_running", "pid": None}
    pid = hb.get("pid")

    running = False
    if pid:
        try:
            os.kill(pid, 0)
            running = True
        except (OSError, ProcessLookupError):
            pass

    if not running:
        return {
            "status": "stopped",
            "pid": pid,
            "last_seen": hb.get("ts", ""),
            "cycles": hb.get("cycles", 0),
        }

    return {
        "status": hb.get("status", "unknown"),
        "pid": pid,
        "cycles": hb.get("cycles", 0),
        "uptime_sec": hb.get("uptime_sec", 0),
        "interval_sec": hb.get("interval_sec", 0),
    }


def _check_last_dispatch() -> Optional[Dict[str, Any]]:
    """Read last dispatch from pointer."""
    data = _read_json(DISPATCH_LATEST)
    if not data:
        return None
    last_dispatch = {
        "task_id": data.get("task_id", ""),
        "status": data.get("status", ""),
        "ts": data.get("ts", ""),
        "author": data.get("author", ""),
    }
    result_path = data.get("result_path")
    if not isinstance(result_path, str) or not result_path.strip():
        return last_dispatch
    candidate = Path(result_path)
    artifact_path = candidate if candidate.is_absolute() else ROOT / candidate
    result = _read_json(artifact_path)
    if not result:
        return last_dispatch
    hashes = get_result_provenance_hashes(result)
    last_dispatch.update(
        {
            "status": get_result_status(result) or last_dispatch["status"],
            "summary": get_result_summary(result) or "",
            "result_path": str(candidate),
            "execution_events": len(get_result_execution_events(result)),
            "provenance_hashes": hashes,
            "authority_mismatches": detect_result_authority_mismatches(result),
            "envelope_seal_verified": get_envelope_seal_verified(result),
        }
    )
    return last_dispatch


def _run_tests() -> Dict[str, Any]:
    """Run all test suites, return results."""
    results = {}
    passed = 0
    failed = 0

    for suite in TEST_SUITES:
        path = VERIFY_DIR / suite
        if not path.exists():
            results[suite] = "missing"
            failed += 1
            continue

        try:
            proc = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(ROOT),
            )
            if proc.returncode == 0:
                results[suite] = "pass"
                passed += 1
            else:
                tail = (proc.stderr or proc.stdout).strip()[-100:]
                results[suite] = f"fail:{tail}"
                failed += 1
        except subprocess.TimeoutExpired:
            results[suite] = "timeout"
            failed += 1
        except Exception as exc:
            results[suite] = f"error:{exc}"
            failed += 1

    return {
        "suites": len(TEST_SUITES),
        "passed": passed,
        "failed": failed,
        "details": results,
    }


def check_health(*, run_tests: bool = False) -> Dict[str, Any]:
    """Run full health check. Returns health report dict."""
    env = _probe_env()
    dispatcher = _check_dispatcher()
    last_dispatch = _check_last_dispatch()
    schemas = _get_schemas()

    queues = {
        "inbox_pending": _count_inbox(),
        "completed": _count_files(COMPLETED, "*.yaml"),
        "rejected": _count_files(REJECTED, "*.yaml"),
        "outbox_results": _count_files(OUTBOX, "*.json"),
    }

    tests_result = None
    if run_tests:
        tests_result = _run_tests()

    issues = []
    if dispatcher["status"] not in ("watching", "not_running", "stopped"):
        issues.append("dispatcher_unhealthy")
    if not schemas:
        issues.append("no_schemas_registered")
    if tests_result and tests_result["failed"] > 0:
        issues.append(f"tests_failed:{tests_result['failed']}")

    status = "healthy" if not issues else "degraded"

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=str(ROOT),
        )
        head_sha = proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None
    except Exception:
        head_sha = None

    ts_val = _utc_now()
    tests_failed = tests_result["failed"] if tests_result else None
    failed_suites = []
    if tests_result and tests_result.get("details"):
        failed_suites = [k for k, v in tests_result["details"].items() if str(v).startswith("fail:")]

    return {
        "schema_version": "health_v1",
        "ts_utc": ts_val,
        "ts": ts_val,
        "producer": "core/health.py",
        "head_sha": head_sha,
        "env": env,
        "status": status,
        "tests_failed": tests_failed,
        "failed_suites": failed_suites,
        "issues": issues,
        "dispatcher": dispatcher,
        "last_dispatch": last_dispatch,
        "queues": queues,
        "schemas": {"count": len(schemas), "names": schemas},
        "tests": {
            "ran": run_tests,
            "suites": len(TEST_SUITES),
            "passed": tests_result["passed"] if tests_result else None,
            "failed": tests_result["failed"] if tests_result else None,
            "details": tests_result.get("details") if tests_result else None,
        },
    }


def _print_human(report: Dict[str, Any]) -> None:
    """Print human-readable health report."""
    print("0luka V.2 Health Check")
    print("=" * 40)

    dispatcher = report["dispatcher"]
    if dispatcher["status"] == "watching":
        print(
            f"Dispatcher:   {dispatcher['status']} (pid {dispatcher['pid']}, "
            f"{dispatcher['cycles']} cycles, uptime {dispatcher['uptime_sec']}s)"
        )
    elif dispatcher["status"] == "stopped":
        print(f"Dispatcher:   stopped (last seen {dispatcher.get('last_seen', 'unknown')})")
    else:
        print(f"Dispatcher:   {dispatcher['status']}")

    last_dispatch = report.get("last_dispatch")
    if last_dispatch:
        print(
            f"Last dispatch: {last_dispatch['task_id']} -> {last_dispatch['status']} "
            f"({last_dispatch['ts']})"
        )
        if last_dispatch.get("summary"):
            print(f"Summary:      {last_dispatch['summary']}")
        if last_dispatch.get("execution_events") is not None:
            print(f"Exec events:  {last_dispatch['execution_events']}")
        mismatches = last_dispatch.get("authority_mismatches") or []
        if mismatches:
            print(f"Authority:    {len(mismatches)} mismatch notes")
        seal_verified = last_dispatch.get("envelope_seal_verified")
        if seal_verified is not None:
            seal_label = "verified" if seal_verified else "INVALID"
            print(f"Envelope:     seal {seal_label}")
    else:
        print("Last dispatch: none")

    queues = report["queues"]
    print(f"\nInbox:        {queues['inbox_pending']} pending")
    print(f"Completed:    {queues['completed']} tasks")
    print(f"Rejected:     {queues['rejected']} tasks")
    print(f"Outbox:       {queues['outbox_results']} results")

    schemas = report["schemas"]
    print(f"\nSchemas:      {schemas['count']} registered ({', '.join(schemas['names'])})")

    tests = report["tests"]
    if tests["ran"]:
        print(f"\nTests:        {tests['passed']}/{tests['suites']} passed")
        if tests.get("details"):
            for suite, result in tests["details"].items():
                icon = "pass" if result == "pass" else "FAIL"
                print(f"  [{icon}] {suite}")
    else:
        print(f"\nTests:        {tests['suites']} suites (use --full to run)")

    print(f"\nStatus: {report['status'].upper()}")
    if report.get("issues"):
        for issue in report["issues"]:
            print(f"  ! {issue}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="0luka System Health Check")
    parser.add_argument("--full", action="store_true", help="Run all test suites")
    parser.add_argument("--env", action="store_true", help="Probe environment only (no test suites)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--cache", action="store_true", help="Write health report cache artifact")
    args = parser.parse_args()

    if args.env:
        env = _probe_env()
        payload = _read_json(CACHE_PATH) or {
            "schema_version": "health_v1",
            "ts_utc": _utc_now(),
            "ts": _utc_now(),
            "producer": "core/health.py",
            "head_sha": None,
            "status": "unknown",
            "tests_failed": None,
            "failed_suites": [],
            "issues": [],
            "dispatcher": {"status": "unknown", "pid": None},
            "last_dispatch": None,
            "queues": {},
            "schemas": {"count": 0, "names": []},
            "tests": {"ran": False, "suites": len(TEST_SUITES), "passed": None, "failed": None, "details": None},
        }
        payload["env"] = env
        _write_json_atomic(CACHE_PATH, payload)
        if args.json:
            print(json.dumps({"env": env}, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"env": env}, indent=2, ensure_ascii=False))
        return 0

    report = check_health(run_tests=args.full)
    if args.cache or args.full:
        _write_json_atomic(CACHE_PATH, report)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human(report)

    return 0 if report["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
