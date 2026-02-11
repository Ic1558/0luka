#!/usr/bin/env python3
"""
Production Smoke Test v1 -- proves the full pipeline works on the real filesystem.

Usage:
    python3 core/smoke.py               # run canary, leave artifacts
    python3 core/smoke.py --clean       # run canary, clean up after
    python3 core/smoke.py --json        # machine-readable output
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

try:
    from core.config import ROOT
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import ROOT

sys.path.insert(0, str(ROOT))

import core.submit as submit_mod
import core.task_dispatcher as dispatcher_mod
from core.verify.no_hardpath_guard import find_hardpath_violations


class SmokeResult:
    def __init__(self) -> None:
        self.steps: List[Dict[str, Any]] = []
        self.task_id: str = ""
        self.passed: bool = True

    def record(self, name: str, ok: bool, detail: str = "") -> bool:
        self.steps.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            self.passed = False
        return ok

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "smoke_v1",
            "ts": _utc_now(),
            "task_id": self.task_id,
            "passed": self.passed,
            "steps": self.steps,
        }


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ts_slug() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def _unique_suffix() -> str:
    return f"{os.getpid():x}{time.monotonic_ns() & 0xFFFFF:05x}"


def _check_no_hardpaths(path: Path) -> List[Dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [{"path": "/", "rule": "invalid_json", "value": str(path)}]
    return find_hardpath_violations(payload)


def run_smoke(*, clean: bool = False) -> SmokeResult:
    # Keep smoke deterministic under test suite module-reload ordering:
    # ensure executor layer writes under current ROOT (temp ROOT in tests).
    try:
        import core.clec_executor as clec_executor

        clec_executor.ROOT = ROOT
    except Exception:
        pass

    result = SmokeResult()
    slug = _ts_slug()
    task_id = f"smoke_{slug}_{_unique_suffix()}"
    result.task_id = task_id
    canary_rel = Path("artifacts") / "smoke" / f"canary_{slug}.txt"
    canary_path = str(canary_rel).replace("\\", "/")
    canary_content = f"smoke test canary - {slug}"

    (ROOT / "artifacts" / "smoke").mkdir(parents=True, exist_ok=True)
    for rel in [
        "artifacts/tasks/open",
        "artifacts/tasks/closed",
        "artifacts/tasks/rejected",
        "observability/artifacts/router_audit",
        "observability/artifacts",
        "observability/logs",
        "interface/inbox",
        "interface/completed",
        "interface/rejected",
        "interface/outbox/tasks",
    ]:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)

    try:
        receipt = submit_mod.submit_task(
            {
                "author": "smoke_test",
                "schema_version": "clec.v1",
                "intent": "smoke.canary",
                "ts_utc": _utc_now(),
                "call_sign": "[Codex]",
                "root": "${0LUKA_ROOT}",
                "created_at_utc": _utc_now(),
                "lane": "task",
                "ops": [
                    {
                        "op_id": "op1",
                        "type": "write_text",
                        "target_path": canary_path,
                        "content": canary_content,
                    }
                ],
                "verify": [],
            },
            task_id=task_id,
        )
        result.record("submit", True, f"task_id={receipt['task_id']}")
    except (submit_mod.SubmitError, Exception) as exc:
        result.record("submit", False, str(exc))
        return result

    inbox_file = ROOT / receipt["inbox_path"]
    open_task = ROOT / "artifacts" / "tasks" / "open" / f"{task_id}.yaml"
    open_task.write_text(f"id: {task_id}\n", encoding="utf-8")

    try:
        dispatch_result = dispatcher_mod.dispatch_one(inbox_file)
        status = str(dispatch_result.get("status", "error"))
        result.record("dispatch", status == "committed", f"status={status}")
    except Exception as exc:
        result.record("dispatch", False, str(exc))
        return result

    outbox_path = ROOT / "interface" / "outbox" / "tasks" / f"{task_id}.result.json"
    if outbox_path.exists():
        result.record("outbox_result", True)
        issues = _check_no_hardpaths(outbox_path)
        result.record("outbox_no_hardpaths", len(issues) == 0, json.dumps(issues[0], ensure_ascii=False) if issues else "")
    else:
        result.record("outbox_result", False, "file not found")

    audit_path = ROOT / "observability" / "artifacts" / "router_audit" / f"{task_id}.json"
    if audit_path.exists():
        result.record("audit_artifact", True)
        issues = _check_no_hardpaths(audit_path)
        result.record("audit_no_hardpaths", len(issues) == 0, json.dumps(issues[0], ensure_ascii=False) if issues else "")
    else:
        result.record("audit_artifact", False, "file not found")

    written_path = ROOT / canary_rel
    if written_path.exists():
        actual = written_path.read_text(encoding="utf-8").strip()
        result.record(
            "written_file",
            actual == canary_content,
            f"path={written_path.as_posix()}",
        )
    else:
        result.record(
            "written_file",
            False,
            f"canary file not found: path={written_path.as_posix()}",
        )

    completed_path = ROOT / "interface" / "completed" / f"{task_id}.yaml"
    result.record("source_moved", completed_path.exists() and not inbox_file.exists())

    latest = ROOT / "observability" / "artifacts" / "dispatch_latest.json"
    if latest.exists():
        try:
            latest_data = json.loads(latest.read_text(encoding="utf-8"))
            result.record("dispatch_latest", latest_data.get("task_id") == task_id)
        except Exception as exc:
            result.record("dispatch_latest", False, str(exc))
    else:
        result.record("dispatch_latest", False, "dispatch_latest missing")

    if clean:
        for path in [outbox_path, audit_path, written_path, completed_path, open_task]:
            if path.exists() and path.is_file():
                path.unlink()
        if latest.exists() and latest.is_file():
            try:
                latest_data = json.loads(latest.read_text(encoding="utf-8"))
                if latest_data.get("task_id") == task_id:
                    latest.unlink()
            except Exception:
                pass

    return result


def _print_human(result: SmokeResult) -> None:
    print("0luka Smoke Test")
    print("=" * 40)
    total = len(result.steps)
    for idx, step in enumerate(result.steps, 1):
        icon = "ok" if step["ok"] else "FAIL"
        detail = f" ({step['detail']})" if step.get("detail") else ""
        print(f"[{idx}/{total}] {step['name']:.<30s} {icon}{detail}")
    print()
    print("Result: PASS" if result.passed else "Result: FAIL")
    print(f"Task:   {result.task_id}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="0luka Production Smoke Test")
    parser.add_argument("--clean", action="store_true", help="Clean up artifacts after test")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    result = run_smoke(clean=args.clean)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        _print_human(result)

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
