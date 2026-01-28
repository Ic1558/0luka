#!/usr/bin/env python3
from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


INTENT_MAP: Dict[str, Dict[str, Any]] = {
    "code.implement": {"executor": "lisa", "required": {"files": "list", "goal": "str"}},
    "code.review": {"executor": "codex", "required": {"range": "str", "focus": "str"}},
    "git.sync": {"executor": "codex", "required": {"branch": "str"}},
    "pr.create": {"executor": "codex", "required": {"title": "str", "body": "str"}},
    "system.verify": {"executor": "liam", "required": {"scope": "str"}},
    "system.audit": {"executor": "liam", "required": {"range": "str"}},
    "task.emit": {
        "executor": "bridge",
        "required": {
            "schema_version": "str",
            "task_id": "str",
            "origin": "str",
            "intent": "str",
            "executor": "str",
            "title": "str",
            "level": "str",
        },
        "optional": {"meta": "dict"},
    },
    "task.progress": {
        "executor": "bridge",
        "required": {"schema_version": "str", "task_id": "str", "status": "str"},
        "optional": {"msg": "str", "pct": "number"},
    },
    "task.result": {
        "executor": "bridge",
        "required": {
            "schema_version": "str",
            "executor": "str",
            "dispatch_task_id": "str",
            "task_id": "str",
            "status": "str",
            "summary": "str",
            "artifacts": "list",
            "diff_stat": "str",
            "verify": "list",
            "exit_code": "number",
            "runtime_ms": "number",
            "evidence_paths": "list",
        },
        "optional": {"links": "dict", "next_actions": "list"},
    },
}


def now_utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"invalid_json: {exc}"


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
    error_path = root / "observability" / "bridge" / "errors" / "bridge_task_processor.jsonl"
    event = {
        "ts": now_utc_iso(),
        "module": "bridge_task_processor",
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


def claim_task(root: Path, task_path: Path) -> Tuple[Optional[Path], Optional[Path]]:
    inbox_path = task_path
    subdir = sanitize_segment(task_path.stem)
    inflight_dir = root / "observability" / "bridge" / "inflight" / subdir
    inflight_dir.mkdir(parents=True, exist_ok=True)

    try:
        inbox_dev = task_path.parent.stat().st_dev
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
    target = inflight_dir / f"{task_path.stem}_{suffix}{task_path.suffix}"
    try:
        os.replace(task_path, target)
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


def move_to_processed(root: Path, task_path: Path, origin: str, suffix: str = "") -> Path:
    target_origin = origin or "unknown"
    processed_dir = root / "observability" / "bridge" / "processed" / target_origin
    processed_dir.mkdir(parents=True, exist_ok=True)
    name = task_path.name
    if suffix:
        name = f"{task_path.stem}_{suffix}{task_path.suffix}"
    processed_path = processed_dir / name
    try:
        shutil.move(str(task_path), str(processed_path))
        return processed_path
    except Exception:
        return task_path


def record_task_id(state_file: Path, task_id: str, source: str) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": now_utc_iso(), "task_id": task_id, "source": source}
    append_jsonl(state_file, record)


def has_task_id(state_file: Path, task_id: str) -> bool:
    if not state_file.exists():
        return False
    try:
        with state_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if str(row.get("task_id")) == task_id:
                    return True
    except Exception:
        return False
    return False


def resolve_ack_path(root: Path, origin: str, task_id: str) -> Path:
    return root / "observability" / "bridge" / "outbox" / origin / f"{task_id}_ack.json"


def normalize_payload(payload: Any) -> Tuple[Any, Optional[str]]:
    if isinstance(payload, str):
        text = payload.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                return json.loads(text), None
            except Exception as exc:
                return payload, f"payload_json_invalid: {exc}"
    return payload, None


def validate_payload(intent: str, payload: Any) -> Tuple[bool, str]:
    spec = INTENT_MAP.get(intent)
    if not spec:
        return False, "intent_not_allowed"
    if not isinstance(payload, dict):
        return False, "payload_missing_fields"

    required = spec.get("required", {})
    optional = spec.get("optional", {})
    for key, expected in required.items():
        if key not in payload:
            return False, "payload_missing_fields"
        value = payload.get(key)
        if expected == "str":
            if not isinstance(value, str) or not value.strip():
                return False, "payload_invalid"
        elif expected == "list":
            if not isinstance(value, list) or not value:
                return False, "payload_invalid"
            if not all(isinstance(item, str) and item.strip() for item in value):
                return False, "payload_invalid"
        elif expected == "dict":
            if not isinstance(value, dict):
                return False, "payload_invalid"
        elif expected == "number":
            if not isinstance(value, (int, float)):
                return False, "payload_invalid"
        else:
            return False, "payload_invalid"

    for key, expected in optional.items():
        if key not in payload:
            continue
        value = payload.get(key)
        if expected == "str":
            if not isinstance(value, str):
                return False, "payload_invalid"
        elif expected == "list":
            if not isinstance(value, list):
                return False, "payload_invalid"
        elif expected == "dict":
            if not isinstance(value, dict):
                return False, "payload_invalid"
        elif expected == "number":
            if not isinstance(value, (int, float)):
                return False, "payload_invalid"

    return True, ""


def load_index(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "updated_at": now_utc_iso(), "tasks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 1, "updated_at": now_utc_iso(), "tasks": {}}
    if not isinstance(data, dict):
        return {"schema_version": 1, "updated_at": now_utc_iso(), "tasks": {}}
    if not isinstance(data.get("tasks"), dict):
        data["tasks"] = {}
    data.setdefault("schema_version", 1)
    data.setdefault("updated_at", now_utc_iso())
    return data


def write_index(path: Path, index: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    index["updated_at"] = now_utc_iso()
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_task(index: Dict[str, Any], task_id: str, updates: Dict[str, Any]) -> None:
    tasks = index.setdefault("tasks", {})
    task = tasks.get(task_id, {})
    task.update(updates)
    task.setdefault("task_id", task_id)
    task["updated_at"] = now_utc_iso()
    tasks[task_id] = task


def append_progress(path: Path, event: Dict[str, Any]) -> None:
    append_jsonl(path, event)


def handle_task_emit(payload: Dict[str, Any], root: Path) -> Tuple[str, Dict[str, Any], str]:
    dashboard_root = root / "observability" / "dashboard"
    index_path = dashboard_root / "tasks.index.json"
    progress_path = dashboard_root / "progress" / f"{payload['task_id']}.jsonl"
    result_path = dashboard_root / "results" / f"{payload['task_id']}.result.json"

    index = load_index(index_path)
    update_task(
        index,
        payload["task_id"],
        {
            "schema_version": payload.get("schema_version"),
            "origin": payload.get("origin"),
            "intent": payload.get("intent"),
            "executor": payload.get("executor"),
            "title": payload.get("title"),
            "level": payload.get("level"),
            "status": "queued",
            "progress_path": str(progress_path),
            "result_path": str(result_path),
            "meta": payload.get("meta", {}),
        },
    )
    write_index(index_path, index)

    event = {
        "ts": now_utc_iso(),
        "status": "queued",
        "msg": "queued",
        "pct": 0,
    }
    append_progress(progress_path, event)
    return "completed", {"index_path": str(index_path), "progress_path": str(progress_path)}, ""


def handle_task_progress(payload: Dict[str, Any], root: Path) -> Tuple[str, Dict[str, Any], str]:
    dashboard_root = root / "observability" / "dashboard"
    index_path = dashboard_root / "tasks.index.json"
    progress_path = dashboard_root / "progress" / f"{payload['task_id']}.jsonl"

    event = {
        "ts": now_utc_iso(),
        "status": payload.get("status"),
        "msg": payload.get("msg", ""),
        "pct": payload.get("pct"),
    }
    append_progress(progress_path, event)

    index = load_index(index_path)
    update_task(
        index,
        payload["task_id"],
        {
            "schema_version": payload.get("schema_version"),
            "status": payload.get("status"),
            "last_progress": now_utc_iso(),
            "progress_path": str(progress_path),
        },
    )
    write_index(index_path, index)
    return "completed", {"progress_path": str(progress_path)}, ""


def handle_task_result(payload: Dict[str, Any], root: Path) -> Tuple[str, Dict[str, Any], str]:
    dashboard_root = root / "observability" / "dashboard"
    index_path = dashboard_root / "tasks.index.json"
    result_path = dashboard_root / "results" / f"{payload['task_id']}.result.json"

    if result_path.exists():
        return "completed", {"result_path": str(result_path), "note": "result_exists"}, ""

    result = dict(payload)
    result["ts"] = now_utc_iso()
    write_json(result_path, result)

    index = load_index(index_path)
    update_task(
        index,
        payload["task_id"],
        {
            "schema_version": payload.get("schema_version"),
            "executor": payload.get("executor"),
            "dispatch_task_id": payload.get("dispatch_task_id"),
            "exit_code": payload.get("exit_code"),
            "runtime_ms": payload.get("runtime_ms"),
            "status": payload.get("status"),
            "result_path": str(result_path),
            "completed_at": now_utc_iso(),
        },
    )
    write_index(index_path, index)
    return "completed", {"result_path": str(result_path)}, ""


def write_dispatch(root: Path, executor: str, task_id: str, payload: Any, meta: Dict[str, Any]) -> Path:
    dispatch_dir = root / "observability" / "bridge" / "outbox" / executor
    dispatch_path = dispatch_dir / f"{task_id}_dispatch.json"
    dispatch = {
        "ts": now_utc_iso(),
        "task_id": task_id,
        "executor": executor,
        "intent": meta["intent"],
        "origin": meta["origin"],
        "reply_to": meta.get("reply_to", ""),
        "payload": payload,
        "status": "queued",
    }
    write_json(dispatch_path, dispatch)
    return dispatch_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    args = ap.parse_args()

    root = Path(os.environ.get("ROOT", os.path.expanduser("~/0luka"))).resolve()
    task_path = Path(args.path).resolve()
    claimed_path, inbox_path = claim_task(root, task_path)
    if claimed_path is None:
        return 0
    task_path = claimed_path

    data, err = load_json(task_path)
    if err:
        processed_path = move_to_processed(root, task_path, "unknown", "invalid")
        record_error(
            root,
            stage="parse_json",
            reason=err,
            inbox_path=inbox_path,
            inflight_path=task_path,
            exc=None,
        )
        ack = {
            "ts": now_utc_iso(),
            "status": "rejected",
            "reason": err,
            "path": str(task_path),
            "processed_path": str(processed_path),
            "reply_to": "unknown",
        }
        ack_path = root / "observability" / "bridge" / "outbox" / "unknown" / "invalid_task_ack.json"
        write_json(ack_path, ack)
        return 2

    task_id = str(data.get("task_id") or "").strip()
    origin = str(data.get("origin") or "").strip()
    intent = str(data.get("intent") or "").strip()
    reply_to = str(data.get("reply_to") or "").strip()
    payload = data.get("payload")
    payload, payload_error = normalize_payload(payload)

    if not task_id or not origin or not intent:
        processed_path = move_to_processed(root, task_path, origin or "unknown", "invalid")
        record_error(
            root,
            stage="validate_fields",
            reason="missing required fields",
            inbox_path=inbox_path,
            inflight_path=task_path,
            task_id=task_id or "",
            agent=origin or "",
        )
        ack = {
            "ts": now_utc_iso(),
            "status": "rejected",
            "reason": "missing required fields",
            "task_id": task_id or "unknown",
            "origin": origin or "unknown",
            "intent": intent or "unknown",
            "processed_path": str(processed_path),
            "reply_to": reply_to or "",
        }
        ack_path = root / "observability" / "bridge" / "outbox" / (origin or "unknown") / "invalid_task_ack.json"
        write_json(ack_path, ack)
        return 2

    loop_guard = {"bridge", "bridge_watch", "bridge_task_processor", "session_recorder"}
    if origin in loop_guard:
        processed_path = move_to_processed(root, task_path, origin, "ignored")
        ack_path = resolve_ack_path(root, origin, task_id)
        ack = {
            "ts": now_utc_iso(),
            "task_id": task_id,
            "origin": origin,
            "intent": intent,
            "status": "ignored",
            "reason": "loop_guard",
            "processed_path": str(processed_path),
            "reply_to": reply_to or "",
        }
        write_json(ack_path, ack)
        return 0

    state_file = root / "observability" / "bridge" / "state" / "task_ids.jsonl"
    if has_task_id(state_file, task_id):
        processed_path = move_to_processed(root, task_path, origin, "duplicate")
        ack_path = resolve_ack_path(root, origin, task_id)
        ack = {
            "ts": now_utc_iso(),
            "task_id": task_id,
            "origin": origin,
            "intent": intent,
            "status": "duplicate",
            "processed_path": str(processed_path),
            "reply_to": reply_to or "",
        }
        write_json(ack_path, ack)
        return 0

    processed_path = move_to_processed(root, task_path, origin)

    if intent not in INTENT_MAP:
        ack_path = resolve_ack_path(root, origin, task_id)
        record_error(
            root,
            stage="validate_intent",
            reason="intent_not_allowed",
            inbox_path=inbox_path,
            inflight_path=task_path,
            task_id=task_id,
            agent=origin,
        )
        ack = {
            "ts": now_utc_iso(),
            "task_id": task_id,
            "origin": origin,
            "intent": intent,
            "status": "rejected",
            "reason": "intent_not_allowed",
            "processed_path": str(processed_path),
            "reply_to": reply_to or "",
        }
        write_json(ack_path, ack)
        record_task_id(state_file, task_id, str(processed_path))
        return 2

    valid, reason = validate_payload(intent, payload)
    if not valid:
        ack_path = resolve_ack_path(root, origin, task_id)
        record_error(
            root,
            stage="validate_payload",
            reason=reason or "payload_invalid",
            inbox_path=inbox_path,
            inflight_path=task_path,
            task_id=task_id,
            agent=origin,
        )
        ack = {
            "ts": now_utc_iso(),
            "task_id": task_id,
            "origin": origin,
            "intent": intent,
            "status": "rejected",
            "reason": reason or "payload_invalid",
            "processed_path": str(processed_path),
            "reply_to": reply_to or "",
        }
        if payload_error:
            ack["payload_warning"] = payload_error
        write_json(ack_path, ack)
        record_task_id(state_file, task_id, str(processed_path))
        return 2

    executor = INTENT_MAP[intent]["executor"]
    ack_path = resolve_ack_path(root, origin, task_id)

    if executor == "bridge" and intent == "task.emit":
        status, result, reason = handle_task_emit(payload, root)
        ack = {
            "ts": now_utc_iso(),
            "task_id": task_id,
            "origin": origin,
            "intent": intent,
            "status": status,
            "reason": reason,
            "processed_path": str(processed_path),
            "reply_to": reply_to or "",
            "result": result,
        }
        if payload_error:
            ack["payload_warning"] = payload_error
        write_json(ack_path, ack)
        record_task_id(state_file, task_id, str(processed_path))
        return 0 if status == "completed" else 2

    if executor == "bridge" and intent == "task.progress":
        status, result, reason = handle_task_progress(payload, root)
        ack = {
            "ts": now_utc_iso(),
            "task_id": task_id,
            "origin": origin,
            "intent": intent,
            "status": status,
            "reason": reason,
            "processed_path": str(processed_path),
            "reply_to": reply_to or "",
            "result": result,
        }
        if payload_error:
            ack["payload_warning"] = payload_error
        write_json(ack_path, ack)
        record_task_id(state_file, task_id, str(processed_path))
        return 0 if status == "completed" else 2

    if executor == "bridge" and intent == "task.result":
        status, result, reason = handle_task_result(payload, root)
        ack = {
            "ts": now_utc_iso(),
            "task_id": task_id,
            "origin": origin,
            "intent": intent,
            "status": status,
            "reason": reason,
            "processed_path": str(processed_path),
            "reply_to": reply_to or "",
            "result": result,
        }
        if payload_error:
            ack["payload_warning"] = payload_error
        write_json(ack_path, ack)
        record_task_id(state_file, task_id, str(processed_path))
        return 0 if status == "completed" else 2

    dispatch_path = write_dispatch(root, executor, task_id, payload, {"intent": intent, "origin": origin, "reply_to": reply_to})
    ack = {
        "ts": now_utc_iso(),
        "task_id": task_id,
        "origin": origin,
        "intent": intent,
        "status": "dispatched",
        "executor": executor,
        "dispatch_path": str(dispatch_path),
        "processed_path": str(processed_path),
        "reply_to": reply_to or "",
    }
    if payload_error:
        ack["payload_warning"] = payload_error
    write_json(ack_path, ack)
    record_task_id(state_file, task_id, str(processed_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
