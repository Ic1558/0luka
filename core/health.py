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
import os
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
]


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
    return {
        "task_id": data.get("task_id", ""),
        "status": data.get("status", ""),
        "ts": data.get("ts", ""),
        "author": data.get("author", ""),
    }


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

    return {
        "schema_version": "health_v1",
        "ts": _utc_now(),
        "status": status,
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
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--cache", action="store_true", help="Write health report cache artifact")
    args = parser.parse_args()

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
