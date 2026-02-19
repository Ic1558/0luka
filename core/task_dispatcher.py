#!/usr/bin/env python3
"""
Task Dispatcher v1 - reads inbox, runs pipeline, writes outbox.

Usage:
    python3 core/task_dispatcher.py                     # process all
    python3 core/task_dispatcher.py --dry-run          # validate only
    python3 core/task_dispatcher.py --file path.yaml   # single file
"""
from __future__ import annotations

import contextlib
import json
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError:
    yaml = None

try:
    from core.config import (
        COMPLETED,
        DEFAULT_WATCH_INTERVAL_SEC,
        DISPATCH_HEARTBEAT,
        DISPATCH_LATEST,
        DISPATCH_LOG,
        INBOX,
        REJECTED,
        ROOT,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import (
        COMPLETED,
        DEFAULT_WATCH_INTERVAL_SEC,
        DISPATCH_HEARTBEAT,
        DISPATCH_LATEST,
        DISPATCH_LOG,
        INBOX,
        REJECTED,
        ROOT,
    )

HEARTBEAT_PATH = DISPATCH_HEARTBEAT
DEFAULT_INTERVAL = DEFAULT_WATCH_INTERVAL_SEC

_stats = {
    "total_dispatched": 0,
    "total_committed": 0,
    "total_rejected": 0,
    "total_error": 0,
    "total_skipped": 0,
}

sys.path.insert(0, str(ROOT))
DISPATCHER_SESSION_RUN_ID = uuid.uuid4().hex

from core.phase1a_resolver import Phase1AResolverError, gate_inbound_envelope
from core.run_provenance import (
    append_event as append_execution_event,
    append_provenance,
    complete_run_provenance,
    init_run_provenance,
)
from core.circuit_breaker import CircuitBreaker, CircuitOpenError
from core.router import Router
from core.timeline import emit_event as _timeline_emit

_dispatch_breaker = CircuitBreaker(
    name="router.execute",
    failure_threshold=3,
    recovery_timeout_sec=60.0,
    max_retries=0,
    backoff_factor=1.5,
)


class DispatchError(RuntimeError):
    pass


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _log_event(event: Dict[str, Any]) -> None:
    """Append one JSON line to dispatch log."""
    DISPATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DISPATCH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _resolve_activity_feed_path() -> Path:
    raw = os.environ.get("LUKA_ACTIVITY_FEED_JSONL", "observability/logs/activity_feed.jsonl").strip()
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return ROOT / p


def _append_runtime_heartbeat_event() -> None:
    # fail-open: observability append must never interrupt dispatch loop
    try:
        feed_path = _resolve_activity_feed_path()
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts_utc": _utc_now(),
            "action": "heartbeat",
            "emit_mode": "runtime_auto",
            "verifier_mode": "operational_proof",
            "tool": "task_dispatcher",
            "run_id": DISPATCHER_SESSION_RUN_ID,
            "ts_epoch_ms": int(time.time_ns() // 1_000_000),
        }
        with feed_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
    except Exception:
        pass


def _emit_activity_event(
    action: str,
    task_id: str,
    *,
    phase_id: str = "GOAL1_ACTIVITY_FEED",
    status_badge: str = "NOT_PROVEN",
    evidence: list | None = None,
) -> None:
    """Emit lifecycle event to activity feed. Fail-open."""
    try:
        feed_path = _resolve_activity_feed_path()
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts_utc": _utc_now(),
            "ts_epoch_ms": int(time.time_ns() // 1_000_000),
            "phase_id": phase_id,
            "action": action,
            "emit_mode": "runtime_auto",
            "verifier_mode": "operational_proof",
            "tool": "task_dispatcher",
            "run_id": DISPATCHER_SESSION_RUN_ID,
            "task_id": task_id,
            "status_badge": status_badge,
            "evidence": evidence or [],
        }
        with feed_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _emit_dispatch_start(task_id: str, trace_id: str, intent: str, module: str) -> float:
    started = time.monotonic()
    _log_event(
        {
            "event": "dispatch.start",
            "ts": _utc_now(),
            "task_id": task_id,
            "trace_id": trace_id,
            "intent": intent,
            "module": module,
        }
    )
    try:
        _timeline_emit(
            trace_id,
            task_id,
            "heartbeat.dispatcher",
            phase="dispatch",
            agent_id="dispatcher",
            extra={"status": "start", "source": "dispatcher"},
        )
    except Exception:
        pass
    return started


def _emit_dispatch_end(
    task_id: str,
    trace_id: str,
    status: str,
    started: float,
    outbox_path: str = "",
    outbox_ref: str = "",
) -> None:
    duration_ms = int((time.monotonic() - started) * 1000)
    _log_event(
        {
            "event": "dispatch.end",
            "ts": _utc_now(),
            "task_id": task_id,
            "trace_id": trace_id,
            "status": status,
            "duration_ms": duration_ms,
            "outbox_path": outbox_path,
            "outbox_ref": outbox_ref,
        }
    )
    try:
        _timeline_emit(
            trace_id,
            task_id,
            "heartbeat.dispatcher",
            phase="dispatch",
            agent_id="dispatcher",
            extra={"status": status, "source": "dispatcher"},
        )
    except Exception:
        pass


def _write_dispatch_pointer(
    task_id: str,
    status: str,
    author: str = "",
    intent: str = "",
    trace_id: str = "",
    result_path: str = "",
    audit_path: str = "",
    source_moved_to: str = "",
) -> None:
    """Write atomic dispatch_latest.json pointer (save-now v2 pattern)."""
    pointer = {
        "schema_version": "dispatch_latest_v1",
        "ts": _utc_now(),
        "task_id": task_id,
        "trace_id": trace_id or task_id,
        "status": status,
        "author": author,
        "intent": intent,
        "result_path": result_path,
        "audit_path": audit_path,
        "source_moved_to": source_moved_to,
        "stats": dict(_stats),
    }
    pointer_str = json.dumps(pointer, ensure_ascii=False, sort_keys=True)
    if "/Users/" in pointer_str or "file:///Users" in pointer_str:
        raise DispatchError("dispatch_pointer_contains_hard_paths")
    DISPATCH_LATEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DISPATCH_LATEST.parent / ".dispatch_latest.tmp"
    tmp.write_text(json.dumps(pointer, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, DISPATCH_LATEST)


def _write_heartbeat(
    status: str,
    interval_sec: int,
    cycles: int,
    last_cycle_tasks: int,
    start_time: float,
) -> None:
    """Write atomic heartbeat for monitors."""
    hb = {
        "schema_version": "dispatcher_heartbeat_v1",
        "ts": _utc_now(),
        "pid": os.getpid(),
        "status": status,
        "interval_sec": interval_sec,
        "cycles": cycles,
        "last_cycle_tasks": last_cycle_tasks,
        "uptime_sec": round(time.monotonic() - start_time, 1),
    }
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HEARTBEAT_PATH.parent / ".dispatcher_heartbeat.tmp"
    tmp.write_text(json.dumps(hb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, HEARTBEAT_PATH)
    _append_runtime_heartbeat_event()


def _wrap_envelope(task: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap a flat inbox task YAML into 0luka.envelope/v1 format."""
    task_id = str(task.get("task_id", "unknown"))
    author = str(task.get("author", "unknown"))
    ts = str(task.get("created_at_utc", _utc_now()))
    lane = str(task.get("lane", "task"))

    wrapped_task = dict(task)
    wrapped_task.setdefault("task_id", task_id)
    wrapped_task.setdefault("intent", str(task.get("intent", "")))
    wrapped_task.setdefault("inputs", {})

    return {
        "v": "0luka.envelope/v1",
        "type": "task.request",
        "trace": {"trace_id": task_id, "ts": ts},
        "source": {"actor": author, "lane": lane},
        "payload": {"task": wrapped_task},
    }


def _already_processed(task_id: str) -> bool:
    outbox_result = ROOT / "interface" / "outbox" / "tasks" / f"{task_id}.result.json"
    completed_file = COMPLETED / f"{task_id}.yaml"
    return outbox_result.exists() or completed_file.exists()


def _move_file(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    os.replace(src, dst)
    return dst


@contextlib.contextmanager
def _cwd(path: Path):
    try:
        prev = Path.cwd()
    except FileNotFoundError:
        prev = Path(__file__).resolve().parents[1]
    os.chdir(path)
    try:
        yield
    finally:
        try:
            os.chdir(prev)
        except FileNotFoundError:
            os.chdir(Path(__file__).resolve().parents[1])


def _build_task_spec(task_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
    # Keep gates deterministic by supplying required keys with minimal, permissive defaults.
    return {
        "id": task_id,
        "intent": str(task.get("intent", "")),
        "actor": {"proposer": str(task.get("author", "unknown"))},
        "verification": {"gates": []},
        "scope": {"allowed_roots": [str(ROOT)]},
        "artifacts": {"outputs": []},
        "capabilities": {"process": {"spawn": True}},
    }


def _check_phase_prerequisites(task_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[str] = []
    raw_requires = task.get("requires")
    if raw_requires is None and isinstance(task.get("meta"), dict):
        raw_requires = task.get("meta", {}).get("requires")

    if raw_requires is None or raw_requires == []:
        return {"ok": True, "missing": []}

    if not isinstance(raw_requires, list):
        return {"ok": False, "missing": [f"unknown:{raw_requires}"]}

    for token in raw_requires:
        if not isinstance(token, str):
            missing.append(f"unknown:{token}")
            continue
        if token.startswith("outbox_exists:"):
            dep_task_id = token.split(":", 1)[1].strip()
            if not dep_task_id:
                missing.append(f"unknown:{token}")
                continue
            dep_outbox = ROOT / "interface" / "outbox" / "tasks" / f"{dep_task_id}.result.json"
            if not dep_outbox.exists():
                missing.append(token)
            continue
        if token.startswith("file_exists:"):
            relpath = token.split(":", 1)[1].strip()
            if not relpath:
                missing.append(f"unknown:{token}")
                continue
            p = Path(relpath)
            if p.is_absolute():
                missing.append(f"unknown:{token}")
                continue
            if not (ROOT / p).exists():
                missing.append(token)
            continue
        missing.append(f"unknown:{token}")

    return {"ok": len(missing) == 0, "missing": missing}


def _build_result_bundle(task_id: str, envelope: Dict[str, Any], task: Dict[str, Any], exec_result: Dict[str, Any]) -> Dict[str, Any]:
    raw_evidence = exec_result.get("evidence", {}) if isinstance(exec_result.get("evidence", {}), dict) else {}
    logs = []
    for item in raw_evidence.get("logs", []) if isinstance(raw_evidence.get("logs", []), list) else []:
        if isinstance(item, str):
            logs.append(item)
        else:
            logs.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
    commands = []
    for item in raw_evidence.get("commands", []) if isinstance(raw_evidence.get("commands", []), list) else []:
        commands.append(item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, sort_keys=True))
    effects = []
    for item in raw_evidence.get("effects", []) if isinstance(raw_evidence.get("effects", []), list) else []:
        effects.append(item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, sort_keys=True))
    evidence = {"logs": logs, "commands": commands, "effects": effects}

    return {
        "task_id": task_id,
        "trace_id": str(envelope.get("trace", {}).get("trace_id", task_id)),
        "status": exec_result.get("status", "error"),
        "summary": f"dispatched:{task_id}",
        "outputs": {"json": {}, "artifacts": []},
        "evidence": evidence,
        "resolved": task.get("resolved", {}),
        "gates": {"observed_fs_writes": [], "observed_processes": []},
        "artifacts": {"outputs": [], "deleted": []},
        "provenance": {
            "trace_id": str(envelope.get("trace", {}).get("trace_id", task_id)),
            "started_at": str(envelope.get("trace", {}).get("ts", _utc_now())),
            "ended_at": _utc_now(),
            "engine": {"name": "core", "version": "phase4a", "host": "local"},
            "hashes": {"inputs_sha256": "dispatch", "outputs_sha256": "dispatch"},
        },
    }


def dispatch_one(file_path: Path, *, dry_run: bool = False) -> Dict[str, Any]:
    task_id = "unknown"
    dispatch_trace_id = "unknown"
    counted_dispatch = False
    dispatch_started_at = 0.0
    pending_verified_evidence = None
    prov_row = None
    try:
        if yaml is None:
            raise DispatchError("missing dependency: pyyaml (pip install pyyaml)")
        if not file_path.exists() or not file_path.is_file():
            raise DispatchError("task_file_not_found")
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise DispatchError("task file must be a YAML object")

        task_id = str(raw.get("task_id", file_path.stem))
        try:
            prov_row = init_run_provenance(
                {
                    "author": str(raw.get("author") or "unknown"),
                    "tool": "DispatcherService",
                    "evidence_refs": [
                        f"file:{file_path}",
                        "command:python3 -m core dispatch --watch",
                    ],
                },
                {"task_id": task_id, "dry_run": dry_run, "task": raw},
            )
            append_execution_event(
                {
                    "type": "execution.started",
                    "category": "execution",
                    "task_id": task_id,
                    "component": "dispatcher",
                    "file": str(file_path),
                }
            )
            _emit_activity_event(
                "started",
                task_id,
                evidence=[{"kind": "log", "ref": "observability/logs/dispatcher.jsonl"}],
            )
        except Exception as exc:
            append_execution_event(
                {
                    "type": "execution.failed",
                    "category": "execution",
                    "task_id": task_id,
                    "component": "dispatcher",
                    "reason": f"missing_provenance:{exc}",
                }
            )
            raise DispatchError(f"run_provenance_required:{exc}") from exc

        if _already_processed(task_id):
            _stats["total_skipped"] += 1
            result = {"task_id": task_id, "status": "skipped", "reason": "already_processed"}
            prov_row = complete_run_provenance(prov_row, result)
            append_provenance(prov_row)
            append_execution_event(
                {
                    "type": "execution.completed",
                    "category": "execution",
                    "task_id": task_id,
                    "component": "dispatcher",
                    "status": "skipped",
                    "input_hash": prov_row.get("input_hash"),
                    "output_hash": prov_row.get("output_hash"),
                }
            )
            _emit_activity_event(
                "completed",
                task_id,
                evidence=[{"kind": "log", "ref": "observability/logs/dispatcher.jsonl"}],
            )
            return result

        envelope = _wrap_envelope(raw)
        dispatch_trace_id = str(envelope.get("trace", {}).get("trace_id", task_id))
        try:
            _timeline_emit(dispatch_trace_id, task_id, "PENDING", phase="dispatch")
        except Exception:
            pass
        dispatch_started_at = _emit_dispatch_start(
            task_id=task_id,
            trace_id=dispatch_trace_id,
            intent=str(raw.get("intent", "")),
            module=str(raw.get("module") or raw.get("schema_version") or "core.task_dispatcher"),
        )
        try:
            gated = gate_inbound_envelope(envelope)
        except Phase1AResolverError as exc:
            try:
                _timeline_emit(dispatch_trace_id, task_id, "DROPPED", phase="gate", detail=str(exc))
            except Exception:
                pass
            result = {"task_id": task_id, "status": "rejected", "reason": f"gate_rejected:{exc}"}
            if not dry_run:
                _move_file(file_path, REJECTED)
                _log_event({**result, "ts": _utc_now(), "file": file_path.name})
                _stats["total_dispatched"] += 1
                _stats["total_rejected"] += 1
                counted_dispatch = True
                _write_dispatch_pointer(
                    task_id=task_id,
                    status="rejected",
                    author=str(raw.get("author", "")),
                    intent=str(raw.get("intent", "")),
                    trace_id=dispatch_trace_id,
                    audit_path=f"observability/artifacts/router_audit/{task_id}.json",
                    source_moved_to=f"interface/rejected/{file_path.name}",
                )
            _emit_dispatch_end(
                task_id=task_id,
                trace_id=dispatch_trace_id,
                status="rejected",
                started=dispatch_started_at,
            )
            prov_row = complete_run_provenance(prov_row, result)
            append_provenance(prov_row)
            append_execution_event(
                {
                    "type": "execution.completed",
                    "category": "execution",
                    "task_id": task_id,
                    "component": "dispatcher",
                    "status": "rejected",
                    "input_hash": prov_row.get("input_hash"),
                    "output_hash": prov_row.get("output_hash"),
                }
            )
            _emit_activity_event(
                "completed",
                task_id,
                evidence=[{"kind": "log", "ref": "observability/logs/dispatcher.jsonl"}],
            )
            return result

        try:
            _timeline_emit(dispatch_trace_id, task_id, "DISPATCHED", phase="gate")
        except Exception:
            pass
        task = gated["payload"]["task"]
        schema_version = str(task.get("schema_version", "")).strip()
        if schema_version != "clec.v1":
            _stats["total_skipped"] += 1
            result = {
                "task_id": task_id,
                "status": "skipped",
                "reason": f"no_executor_for_schema:{schema_version or 'none'}",
            }
            if not dry_run:
                _move_file(file_path, REJECTED)
                _log_event({**result, "ts": _utc_now(), "file": file_path.name})
            _emit_dispatch_end(
                task_id=task_id,
                trace_id=dispatch_trace_id,
                status="skipped",
                started=dispatch_started_at,
            )
            prov_row = complete_run_provenance(prov_row, result)
            append_provenance(prov_row)
            append_execution_event(
                {
                    "type": "execution.completed",
                    "category": "execution",
                    "task_id": task_id,
                    "component": "dispatcher",
                    "status": "skipped",
                    "input_hash": prov_row.get("input_hash"),
                    "output_hash": prov_row.get("output_hash"),
                }
            )
            _emit_activity_event(
                "completed",
                task_id,
                evidence=[{"kind": "log", "ref": "observability/logs/dispatcher.jsonl"}],
            )
            return result

        prereq_result = _check_phase_prerequisites(task_id, task)
        if not prereq_result.get("ok"):
            missing = prereq_result.get("missing", [])
            result = {"task_id": task_id, "status": "blocked", "reason": missing}
            _emit_activity_event(
                "blocked",
                task_id,
                phase_id="GOAL3_GATE_ENFORCE",
                evidence=[{"kind": "prerequisite", "ref": str(item)} for item in missing],
            )
            if not dry_run:
                _move_file(file_path, REJECTED)
                _log_event({**result, "ts": _utc_now(), "file": file_path.name})
            _stats["total_dispatched"] += 1
            _stats["total_rejected"] += 1
            counted_dispatch = True
            _write_dispatch_pointer(
                task_id=task_id,
                status="blocked",
                author=str(task.get("author", "")),
                intent=str(task.get("intent", "")),
                trace_id=dispatch_trace_id,
                audit_path=f"observability/artifacts/router_audit/{task_id}.json",
                source_moved_to=f"interface/rejected/{file_path.name}",
            )
            _emit_dispatch_end(
                task_id=task_id,
                trace_id=dispatch_trace_id,
                status="blocked",
                started=dispatch_started_at,
            )
            prov_row = complete_run_provenance(prov_row, result)
            append_provenance(prov_row)
            append_execution_event(
                {
                    "type": "execution.completed",
                    "category": "execution",
                    "task_id": task_id,
                    "component": "dispatcher",
                    "status": "blocked",
                    "input_hash": prov_row.get("input_hash"),
                    "output_hash": prov_row.get("output_hash"),
                }
            )
            _emit_activity_event(
                "completed",
                task_id,
                evidence=[{"kind": "log", "ref": "observability/logs/dispatcher.jsonl"}],
            )
            return result

        router = Router()
        try:
            exec_result = _dispatch_breaker.call(router.execute, task)
        except CircuitOpenError as exc:
            try:
                _timeline_emit(dispatch_trace_id, task_id, "DROPPED", phase="dispatch", detail=str(exc))
            except Exception:
                pass
            result = {"task_id": task_id, "status": "error", "reason": f"circuit_open:{exc}"}
            _stats["total_dispatched"] += 1
            _stats["total_error"] += 1
            counted_dispatch = True
            _emit_dispatch_end(task_id=task_id, trace_id=dispatch_trace_id, status="error", started=dispatch_started_at)
            prov_row = complete_run_provenance(prov_row, result)
            append_provenance(prov_row)
            _emit_activity_event(
                "failed",
                task_id,
                evidence=[
                    {"kind": "error", "ref": "dispatch_error:CircuitOpenError"},
                    {"kind": "reason", "ref": f"circuit_open:{exc}"},
                ],
            )
            return result
        if dry_run:
            _stats["total_skipped"] += 1
            _emit_dispatch_end(
                task_id=task_id,
                trace_id=dispatch_trace_id,
                status="dry_run_ok",
                started=dispatch_started_at,
            )
            result = {"task_id": task_id, "status": "dry_run_ok", "exec_status": exec_result.get("status")}
            prov_row = complete_run_provenance(prov_row, result)
            append_provenance(prov_row)
            append_execution_event(
                {
                    "type": "execution.completed",
                    "category": "execution",
                    "task_id": task_id,
                    "component": "dispatcher",
                    "status": "dry_run_ok",
                    "input_hash": prov_row.get("input_hash"),
                    "output_hash": prov_row.get("output_hash"),
                }
            )
            _emit_activity_event(
                "completed",
                task_id,
                evidence=[{"kind": "log", "ref": "observability/logs/dispatcher.jsonl"}],
            )
            return result

        result_bundle = _build_result_bundle(task_id, envelope, task, exec_result)
        task_spec = _build_task_spec(task_id, task)

        with _cwd(ROOT):
            audit_result = router.audit(task_spec, result_bundle)

        if audit_result.get("status") == "committed":
            _move_file(file_path, COMPLETED)
        else:
            _move_file(file_path, REJECTED)

        final = {"task_id": task_id, "status": audit_result.get("status", "error"), "audit": audit_result}
        _log_event({**final, "ts": _utc_now(), "file": file_path.name})
        _stats["total_dispatched"] += 1
        counted_dispatch = True
        if audit_result.get("status") == "committed":
            _stats["total_committed"] += 1
            _write_dispatch_pointer(
                task_id=task_id,
                status="committed",
                author=str(task.get("author", "")),
                intent=str(task.get("intent", "")),
                trace_id=dispatch_trace_id,
                result_path=f"interface/outbox/tasks/{task_id}.result.json",
                audit_path=f"observability/artifacts/router_audit/{task_id}.json",
                source_moved_to=f"interface/completed/{file_path.name}",
            )
            _outbox = ROOT / "interface" / "outbox" / "tasks" / f"{task_id}.result.json"
            if _outbox.exists():
                pending_verified_evidence = [
                    {"kind": "file", "ref": f"interface/outbox/tasks/{task_id}.result.json"},
                    {"kind": "audit", "ref": f"observability/artifacts/router_audit/{task_id}.json"},
                ]
        else:
            _stats["total_rejected"] += 1
            _write_dispatch_pointer(
                task_id=task_id,
                status=str(audit_result.get("status", "rejected")),
                author=str(task.get("author", "")),
                intent=str(task.get("intent", "")),
                trace_id=dispatch_trace_id,
                audit_path=f"observability/artifacts/router_audit/{task_id}.json",
                source_moved_to=f"interface/rejected/{file_path.name}",
            )
        final_status = str(audit_result.get("status", "error"))
        final_outbox_path = f"interface/outbox/tasks/{task_id}.result.json" if final_status == "committed" else ""
        _emit_dispatch_end(
            task_id=task_id,
            trace_id=dispatch_trace_id,
            status=final_status,
            started=dispatch_started_at,
            outbox_path=final_outbox_path,
            outbox_ref="ref://interface/outbox" if final_outbox_path else "",
        )
        prov_row = complete_run_provenance(prov_row, final)
        append_provenance(prov_row)
        append_execution_event(
            {
                "type": "execution.completed",
                "category": "execution",
                "task_id": task_id,
                "component": "dispatcher",
                "status": final_status,
                "input_hash": prov_row.get("input_hash"),
                "output_hash": prov_row.get("output_hash"),
            }
        )
        _emit_activity_event(
            "completed",
            task_id,
            evidence=[{"kind": "log", "ref": "observability/logs/dispatcher.jsonl"}],
        )
        if pending_verified_evidence:
            _emit_activity_event(
                "verified",
                task_id,
                status_badge="PROVEN",
                evidence=pending_verified_evidence,
            )
        return final

    except Exception as exc:
        if not counted_dispatch:
            _stats["total_dispatched"] += 1
        _stats["total_error"] += 1
        error_result = {"task_id": task_id, "status": "error", "reason": f"unhandled:{type(exc).__name__}:{exc}"}
        _log_event({**error_result, "ts": _utc_now(), "file": file_path.name})
        with contextlib.suppress(Exception):
            _write_dispatch_pointer(
                task_id=task_id,
                status="error",
                trace_id=dispatch_trace_id,
                source_moved_to=f"interface/inbox/{file_path.name}",
            )
        if dispatch_started_at > 0:
            _emit_dispatch_end(
                task_id=task_id,
                trace_id=dispatch_trace_id,
                status="error",
                started=dispatch_started_at,
            )
        append_execution_event(
            {
                "type": "execution.failed",
                "category": "execution",
                "task_id": task_id,
                "component": "dispatcher",
                "reason": f"dispatch_error:{type(exc).__name__}:{exc}",
            }
        )
        _emit_activity_event(
            "failed",
            task_id,
            evidence=[{"kind": "error", "ref": f"dispatch_error:{type(exc).__name__}"}],
        )
        if prov_row:
            with contextlib.suppress(Exception):
                row = complete_run_provenance(prov_row, error_result)
                append_provenance(row)
        return error_result


def dispatch_all(*, dry_run: bool = False) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not INBOX.exists():
        return results
    for file_path in sorted(INBOX.glob("task_*.yaml")):
        if file_path.is_file():
            results.append(dispatch_one(file_path, dry_run=dry_run))
    return results


def watch(*, interval: int = DEFAULT_INTERVAL, max_cycles: int = 0) -> None:
    """Watch inbox and dispatch continuously."""
    if interval < 1:
        raise DispatchError("interval must be >= 1")

    shutdown = {"requested": False}

    def _handle_signal(_signum, _frame):
        shutdown["requested"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    start_time = time.monotonic()
    cycles = 0

    _write_heartbeat("starting", interval, 0, 0, start_time)
    _log_event({"ts": _utc_now(), "event": "watch_start", "interval": interval, "pid": os.getpid()})

    while not shutdown["requested"]:
        cycles += 1
        results = dispatch_all()
        task_count = len(results)

        _write_heartbeat("watching", interval, cycles, task_count, start_time)
        if task_count > 0:
            committed = sum(1 for row in results if row.get("status") == "committed")
            _log_event(
                {
                    "ts": _utc_now(),
                    "event": "watch_cycle",
                    "cycle": cycles,
                    "processed": task_count,
                    "committed": committed,
                }
            )

        if max_cycles > 0 and cycles >= max_cycles:
            break

        for _ in range(interval * 10):
            if shutdown["requested"]:
                break
            time.sleep(0.1)

    _write_heartbeat("stopped", interval, cycles, 0, start_time)
    _log_event({"ts": _utc_now(), "event": "watch_stop", "cycles": cycles, "pid": os.getpid()})


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Task Dispatcher v1")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't execute or move files")
    parser.add_argument("--file", type=str, help="Process a single file instead of scanning inbox")
    parser.add_argument("--watch", action="store_true", help="Watch inbox continuously")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="Watch interval in seconds")
    args = parser.parse_args()

    if args.watch:
        watch(interval=args.interval)
        return 0

    if args.file:
        result = dispatch_one(Path(args.file), dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("status") in ("committed", "skipped", "dry_run_ok") else 1

    results = dispatch_all(dry_run=args.dry_run)
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    failed = sum(1 for result in results if result.get("status") == "error")
    print(f"\nProcessed: {len(results)}  Failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
