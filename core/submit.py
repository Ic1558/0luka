#!/usr/bin/env python3
"""
Task Submit API v1 - programmatic entry point for task submission.

Usage (Python):
    from core.submit import submit_task
    receipt = submit_task({
        "intent": "code.review",
        "author": "openwork",
        "schema_version": "clec.v1",
        "ops": [{"op_id": "op1", "type": "run", "command": "git status"}],
    })
    print(receipt["task_id"])

Usage (CLI):
    echo '{"intent":"test","author":"cli"}' | python3 core/submit.py
    python3 core/submit.py --file task.yaml
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(os.environ.get("ROOT") or Path(__file__).resolve().parents[1])
INBOX = ROOT / "interface" / "inbox"
OUTBOX = ROOT / "interface" / "outbox" / "tasks"
COMPLETED = ROOT / "interface" / "completed"

sys.path.insert(0, str(ROOT))

from core.verify.no_hardpath_guard import find_hardpath_violations


class SubmitError(RuntimeError):
    pass


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _generate_task_id(author: str = "unknown") -> str:
    """Generate unique task_id: task_YYYYMMDD_HHMMSS_<short_hash>."""
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    noise = hashlib.sha256(f"{ts}{author}{os.getpid()}{time.monotonic_ns()}".encode("utf-8")).hexdigest()[:6]
    return f"task_{ts}_{noise}"


def _is_envelope(data: Dict[str, Any]) -> bool:
    return (
        isinstance(data.get("v"), str)
        and str(data["v"]).startswith("0luka.envelope")
        and isinstance(data.get("payload"), dict)
        and isinstance(data.get("trace"), dict)
        and isinstance(data.get("source"), dict)
    )


def _wrap_envelope(task: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    author = str(task.get("author", "unknown"))
    ts = str(task.get("created_at_utc", _utc_now()))
    lane = str(task.get("lane", "task"))

    wrapped = dict(task)
    wrapped["task_id"] = task_id
    wrapped.setdefault("intent", str(task.get("intent", "")))
    wrapped.setdefault("inputs", {})

    return {
        "v": "0luka.envelope/v1",
        "type": "task.request",
        "trace": {"trace_id": task_id, "ts": ts},
        "source": {"actor": author, "lane": lane},
        "payload": {"task": wrapped},
    }


def _check_duplicate(task_id: str) -> Optional[str]:
    if (INBOX / f"{task_id}.yaml").exists():
        return "duplicate_in_inbox"
    if (OUTBOX / f"{task_id}.result.json").exists():
        return "already_in_outbox"
    if (COMPLETED / f"{task_id}.yaml").exists():
        return "already_completed"
    return None


def submit_task(task: Dict[str, Any], *, task_id: Optional[str] = None) -> Dict[str, Any]:
    """Submit a task to inbox and return receipt."""
    if not isinstance(task, dict):
        raise SubmitError("task must be a dict")

    if _is_envelope(task):
        envelope = dict(task)
        trace = dict(envelope.get("trace") or {})
        payload = dict(envelope.get("payload") or {})
        inner_task = dict(payload.get("task") or {})
        actor = str((envelope.get("source") or {}).get("actor", "unknown"))

        tid = str(task_id or inner_task.get("task_id") or "").strip() or _generate_task_id(actor)
        inner_task["task_id"] = tid
        payload["task"] = inner_task
        trace["trace_id"] = str(trace.get("trace_id") or tid)
        trace.setdefault("ts", _utc_now())
        envelope["payload"] = payload
        envelope["trace"] = trace
    else:
        author = str(task.get("author", "unknown"))
        tid = str(task_id or task.get("task_id") or "").strip() or _generate_task_id(author)
        envelope = _wrap_envelope(task, tid)

    violations = find_hardpath_violations(envelope)
    if violations:
        first = violations[0]
        raise SubmitError(f"hard_path_detected:{first['path']}:{first['rule']}")

    dup = _check_duplicate(tid)
    if dup:
        raise SubmitError(f"duplicate:{dup}:{tid}")

    INBOX.mkdir(parents=True, exist_ok=True)
    out_path = INBOX / f"{tid}.yaml"
    tmp_path = INBOX / f".{tid}.tmp"

    inner_task = dict((envelope.get("payload") or {}).get("task") or {})
    if yaml is not None:
        content = yaml.dump(inner_task, default_flow_style=False, allow_unicode=True, sort_keys=False)
    else:
        content = json.dumps(inner_task, indent=2, ensure_ascii=False) + "\n"

    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, out_path)

    trace_id = str((envelope.get("trace") or {}).get("trace_id", tid))
    return {
        "status": "submitted",
        "task_id": tid,
        "trace_id": trace_id,
        "inbox_path": str(out_path.relative_to(ROOT)),
        "ts": _utc_now(),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Task Submit API v1")
    parser.add_argument("--file", type=str, help="Submit from YAML/JSON file")
    args = parser.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.exists() or not path.is_file():
            print(json.dumps({"status": "error", "reason": "file_not_found"}))
            return 1
        raw = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml") and yaml is not None:
            task = yaml.safe_load(raw)
        else:
            task = json.loads(raw)
    else:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({"status": "error", "reason": "empty_stdin"}))
            return 1
        task = json.loads(raw)

    try:
        receipt = submit_task(task)
    except SubmitError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}))
        return 1

    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
