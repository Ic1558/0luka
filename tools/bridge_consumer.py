#!/usr/bin/env python3
from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def now_utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")


def format_exception(exc: BaseException) -> str:
    message = str(exc)
    if len(message) > 240:
        message = message[:237] + "..."
    return f"{exc.__class__.__name__}: {message}"


def record_error(
    root: Path,
    *,
    stage: str,
    reason: str,
    inbox_path: Optional[Path] = None,
    inflight_path: Optional[Path] = None,
    task_id: str = "",
    agent: str = "",
    exc: Optional[BaseException] = None,
) -> None:
    error_path = root / "observability" / "bridge" / "errors" / "bridge_consumer.jsonl"
    event = {
        "ts": now_utc_iso(),
        "module": "bridge_consumer",
        "event": "error",
        "stage": stage,
        "reason": reason,
        "inbox_path": str(inbox_path) if inbox_path else "",
        "inflight_path": str(inflight_path) if inflight_path else "",
        "task_id": task_id or "",
        "agent": agent or "",
        "exception": format_exception(exc) if exc else "",
    }
    append_jsonl(error_path, event)


def sanitize_segment(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    cleaned = cleaned.strip("_")
    if not cleaned:
        return "unknown"
    if len(cleaned) > 40:
        return cleaned[:40]
    return cleaned


def claim_dispatch(root: Path, dispatch_path: Path) -> Tuple[Optional[Path], Optional[Path]]:
    inbox_path = dispatch_path
    subdir = sanitize_segment(dispatch_path.stem)
    inflight_dir = root / "observability" / "bridge" / "inflight" / subdir
    inflight_dir.mkdir(parents=True, exist_ok=True)

    try:
        inbox_dev = dispatch_path.parent.stat().st_dev
        inflight_dev = inflight_dir.stat().st_dev
    except Exception as exc:
        record_error(
            root,
            stage="claim",
            reason="stat_failed",
            inbox_path=inbox_path,
            inflight_path=inflight_dir,
            exc=exc,
        )
        return None, None

    if inbox_dev != inflight_dev:
        record_error(
            root,
            stage="claim",
            reason="cross_device",
            inbox_path=inbox_path,
            inflight_path=inflight_dir,
        )
        return None, None

    suffix = f"claim_{int(time.time() * 1000)}_{os.getpid()}"
    target = inflight_dir / f"{dispatch_path.stem}_{suffix}{dispatch_path.suffix}"
    try:
        os.replace(dispatch_path, target)
        return target, inbox_path
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        reason = "cross_device" if exc.errno == errno.EXDEV else "claim_failed"
        record_error(
            root,
            stage="claim",
            reason=reason,
            inbox_path=inbox_path,
            inflight_path=target,
            exc=exc,
        )
        return None, None


def move_to_processed(root: Path, path: Path, origin: str, suffix: str = "") -> Path:
    target_origin = origin or "unknown"
    processed_dir = root / "observability" / "bridge" / "processed" / target_origin
    processed_dir.mkdir(parents=True, exist_ok=True)
    name = path.name
    if suffix:
        name = f"{path.stem}_{suffix}{path.suffix}"
    processed_path = processed_dir / name
    try:
        shutil.move(str(path), str(processed_path))
        return processed_path
    except Exception:
        return path


def list_dispatches(root: Path, executor: str = "") -> List[Path]:
    if executor:
        pattern = Path("observability/bridge/outbox") / executor / "*_dispatch.json"
        paths = list(root.glob(str(pattern)))
    else:
        pattern = "observability/bridge/outbox/*/*_dispatch.json"
        paths = list(root.glob(pattern))
    paths = [path for path in paths if path.is_file()]
    paths.sort(key=lambda p: p.stat().st_mtime)
    return paths


def create_task_message(root: Path, origin: str, intent: str, payload: Dict[str, Any]) -> Path:
    task_id = uuid.uuid4().hex
    ts_iso = now_utc_iso()
    ts_file = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    inbox_dir = root / "observability" / "bridge" / "inbox" / origin
    inbox_dir.mkdir(parents=True, exist_ok=True)
    task_path = inbox_dir / f"{ts_file}_{task_id}.task.json"
    message = {
        "task_id": task_id,
        "ts": ts_iso,
        "origin": origin,
        "intent": intent,
        "payload": payload,
        "reply_to": origin,
    }
    write_json(task_path, message)
    return task_path


def create_exec_artifact(root: Path, executor: str, dispatch_task_id: str, dispatch_path: Path) -> Path:
    artifact_dir = root / "interface" / "inbox" / "tasks" / executor
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{dispatch_task_id}_exec.json"
    payload = {
        "ts": now_utc_iso(),
        "executor": executor,
        "task_id": dispatch_task_id,
        "status": "queued",
        "dispatch_path": str(dispatch_path),
    }
    write_json(artifact_path, payload)
    return artifact_path


def write_latest(root: Path, status: str, note: str, last_file: str, last_event: Optional[Dict[str, Any]] = None) -> None:
    telemetry_path = root / "observability" / "telemetry" / "bridge_consumer.latest.json"
    data: Dict[str, Any] = {
        "ts": now_utc_iso(),
        "module": "bridge_consumer",
        "status": status,
        "note": note,
        "last_file": last_file,
    }
    if last_event:
        data["last_event"] = last_event
    write_json(telemetry_path, data)


TASK_ARTIFACTS = None


def load_task_artifacts(root: Path):
    if str(root) not in sys.path:
        sys.path.append(str(root))
    try:
        from observability.tools.memory import task_artifacts

        return task_artifacts
    except Exception:
        return None


def handle_dispatch(root: Path, dispatch_path: Path, original_path: Path) -> bool:
    data, err = load_json(dispatch_path)
    if err:
        processed_path = move_to_processed(root, dispatch_path, "unknown", "invalid")
        record_error(
            root,
            stage="parse_json",
            reason=err,
            inbox_path=original_path,
            inflight_path=processed_path,
            exc=None,
        )
        return False

    dispatch_task_id = str(data.get("task_id") or "").strip()
    executor = str(data.get("executor") or "").strip()
    origin = str(data.get("origin") or "").strip()
    intent = str(data.get("intent") or "").strip()
    if not dispatch_task_id or not executor or not intent:
        processed_path = move_to_processed(root, dispatch_path, origin or "unknown", "invalid")
        record_error(
            root,
            stage="validate_fields",
            reason="missing required fields",
            inbox_path=original_path,
            inflight_path=processed_path,
            task_id=dispatch_task_id,
            agent=origin,
        )
        return False

    trace_id = dispatch_task_id
    payload = data.get("payload") or {}
    if TASK_ARTIFACTS and executor in {"lisa", "codex"}:
        trace_id = TASK_ARTIFACTS.ensure_trace_id(dispatch_task_id, data.get("trace_id"))
        goal = ""
        if isinstance(payload, dict):
            goal = str(payload.get("goal") or payload.get("title") or payload.get("summary") or "")
        plan = {
            "trace_id": trace_id,
            "intent": intent,
            "level": "L3",
            "goal": goal or f"dispatch {intent}",
            "executor": executor,
            "origin": origin,
            "payload": payload,
            "subtasks": [
                {
                    "id": "execute",
                    "executor": executor,
                    "intent": intent,
                    "description": "Execute dispatched payload",
                    "success_criteria": ["execution complete"],
                }
            ],
            "success_criteria": ["execution complete"],
            "created_utc": now_utc_iso(),
        }
        try:
            TASK_ARTIFACTS.write_plan_artifacts(
                root,
                trace_id=trace_id,
                task_id=dispatch_task_id,
                agent_id=executor,
                goal=plan.get("goal", ""),
                plan=plan,
            )
        except Exception as exc:
            record_error(
                root,
                stage="plan_artifact",
                reason="plan_artifact_failed",
                inbox_path=original_path,
                inflight_path=dispatch_path,
                task_id=dispatch_task_id,
                agent=executor,
                exc=exc,
            )

    start = time.time()
    try:
        artifact_path = create_exec_artifact(root, executor, dispatch_task_id, original_path)
    except Exception as exc:
        record_error(
            root,
            stage="artifact",
            reason="artifact_write_failed",
            inbox_path=original_path,
            inflight_path=dispatch_path,
            task_id=dispatch_task_id,
            agent=executor,
            exc=exc,
        )
        artifact_path = dispatch_path

    progress_payload = {
        "schema_version": "1.1",
        "task_id": dispatch_task_id,
        "trace_id": trace_id,
        "status": "running",
        "msg": "exec endpoint queued",
        "pct": 20,
    }
    create_task_message(root, executor, "task.progress", progress_payload)

    progress_payload_final = {
        "schema_version": "1.1",
        "task_id": dispatch_task_id,
        "trace_id": trace_id,
        "status": "ok",
        "msg": "exec endpoint queued",
        "pct": 100,
    }
    create_task_message(root, executor, "task.progress", progress_payload_final)

    runtime_ms = int((time.time() - start) * 1000)
    result_payload = {
        "schema_version": "1.1",
        "executor": executor,
        "dispatch_task_id": dispatch_task_id,
        "task_id": dispatch_task_id,
        "trace_id": trace_id,
        "status": "ok",
        "summary": "exec endpoint queued",
        "artifacts": [str(artifact_path)],
        "diff_stat": "n/a",
        "verify": ["exec_endpoint"],
        "exit_code": 0,
        "runtime_ms": runtime_ms,
        "evidence_paths": [str(artifact_path)],
        "links": {},
    }
    create_task_message(root, executor, "task.result", result_payload)

    move_to_processed(root, dispatch_path, origin or executor)
    return True


def load_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"invalid_json: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--executor", default="")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=int(os.environ.get("BRIDGE_CONSUMER_INTERVAL", "10")))
    args = ap.parse_args()

    root = Path(os.environ.get("ROOT", os.path.expanduser("~/0luka"))).resolve()
    global TASK_ARTIFACTS
    TASK_ARTIFACTS = load_task_artifacts(root)
    executor = args.executor
    interval = max(args.interval, 1)
    _ = args.loop

    while True:
        dispatches = list_dispatches(root, executor)
        if not dispatches:
            write_latest(root, "idle", "no_new_files", "")
            if args.once:
                return 0
            time.sleep(interval)
            continue

        last_file = ""
        for dispatch_path in dispatches:
            claimed_path, original_path = claim_dispatch(root, dispatch_path)
            if claimed_path is None:
                continue
            last_file = str(dispatch_path)
            last_event = {"kind": "dispatch", "path": str(dispatch_path), "ts": now_utc_iso()}
            if original_path is None:
                original_path = dispatch_path
            if handle_dispatch(root, claimed_path, original_path):
                write_latest(root, "ok", "consumed", last_file, last_event)
            else:
                write_latest(root, "error", "dispatch_failed", last_file, last_event)
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
