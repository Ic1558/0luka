#!/usr/bin/env python3
"""Bridge adapter: convert bridge-consumer task shape into core submit envelope."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

from core.submit import SubmitError, submit_task


class BridgeError(RuntimeError):
    pass


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def to_core_task(task: dict[str, Any]) -> dict[str, Any]:
    """Map bridge task payload into core submit payload."""
    if not isinstance(task, dict):
        raise BridgeError("bridge_task_must_be_object")

    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    trace = task.get("trace") if isinstance(task.get("trace"), dict) else {}
    source = task.get("source") if isinstance(task.get("source"), dict) else {}

    task_id = str(task.get("task_id") or task.get("id") or trace.get("trace_id") or "").strip()
    author = str(task.get("author") or source.get("actor") or task.get("executor") or "bridge").strip()
    created_at = str(task.get("created_at_utc") or task.get("ts_utc") or trace.get("ts") or _utc_now())
    lane = str(task.get("lane") or source.get("lane") or "task")
    intent = str(task.get("intent") or payload.get("intent") or "")
    schema_version = str(task.get("schema_version") or payload.get("schema_version") or "clec.v1")
    ops = task.get("ops") if isinstance(task.get("ops"), list) else payload.get("ops")
    verify = task.get("verify") if isinstance(task.get("verify"), list) else payload.get("verify")

    mapped = {
        "author": author,
        "intent": intent,
        "schema_version": schema_version,
        "ts_utc": created_at,
        "call_sign": str(task.get("call_sign") or payload.get("call_sign") or f"[{author.capitalize()}]"),
        "root": str(task.get("root") or payload.get("root") or ""),
        "created_at_utc": created_at,
        "lane": lane,
        "ops": ops if isinstance(ops, list) else [],
        "verify": verify if isinstance(verify, list) else [],
    }
    if task_id:
        mapped["task_id"] = task_id
    return mapped


def submit_bridge_task(task: dict[str, Any], *, task_id: str | None = None) -> dict[str, Any]:
    """Convert bridge format and submit into core inbox."""
    mapped = to_core_task(task)
    explicit_task_id = task_id or (str(mapped.get("task_id", "")).strip() or None)
    try:
        return submit_task(mapped, task_id=explicit_task_id)
    except SubmitError as exc:
        raise BridgeError(str(exc)) from exc


def load_bridge_task(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise BridgeError("bridge_task_file_not_found")
    raw = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise BridgeError("pyyaml_required_for_yaml")
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise BridgeError("bridge_task_invalid_root")
    return data


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bridge -> core submit adapter")
    parser.add_argument("--file", type=str, required=True, help="Bridge task JSON/YAML")
    parser.add_argument("--task-id", type=str, default=None)
    args = parser.parse_args()

    try:
        task = load_bridge_task(Path(args.file))
        receipt = submit_bridge_task(task, task_id=args.task_id)
    except BridgeError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}))
        return 1

    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

