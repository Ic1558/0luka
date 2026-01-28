#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


def now_utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_trace_id(task_id: str | None, existing: str | None = None) -> str:
    if task_id:
        return task_id
    if existing and existing not in {"trace-unknown", ""}:
        return existing
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    return f"trace-{stamp}_{uuid.uuid4().hex[:8]}"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def task_dir(root: Path, trace_id: str) -> Path:
    return root / "observability" / "artifacts" / "tasks" / trace_id


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_plan_md(plan: Dict[str, Any]) -> str:
    goal = plan.get("goal") or ""
    lines = ["# Plan", "", f"Goal: {goal}", ""]
    subtasks = plan.get("subtasks") or []
    if subtasks:
        lines.append("Subtasks:")
        for sub in subtasks:
            desc = sub.get("description") or sub.get("id") or "subtask"
            executor = sub.get("executor") or ""
            if executor:
                lines.append(f"- {desc} (executor: {executor})")
            else:
                lines.append(f"- {desc}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def update_meta(
    meta_path: Path,
    *,
    trace_id: str,
    task_id: str | None,
    agent_id: str,
    goal: str | None,
    status: str,
    ts_key: str,
    paths: Dict[str, str],
) -> Dict[str, Any]:
    meta = read_json(meta_path)
    meta.setdefault("trace_id", trace_id)
    meta["task_id"] = task_id or meta.get("task_id")
    if goal:
        meta["goal"] = goal
    meta["agent_id_owner"] = agent_id
    meta["status"] = status
    meta[ts_key] = now_utc_iso()
    meta.setdefault("paths", {})
    meta["paths"].update(paths)
    meta.setdefault("save_now", {})
    write_json(meta_path, meta)
    return meta


def update_save_now(meta: Dict[str, Any], status: str, error: str | None) -> Dict[str, Any]:
    meta.setdefault("save_now", {})
    meta["save_now"]["last_status"] = status
    meta["save_now"]["last_ts"] = now_utc_iso()
    meta["save_now"]["last_error"] = error or ""
    return meta


def log_save_now_failure(root: Path, entry: Dict[str, Any]) -> None:
    log_path = root / "observability" / "logs" / "save_now_failures.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_save_now(
    root: Path,
    *,
    agent_id: str,
    trace_id: str,
    phase: str,
    task_id: str | None,
    files: Iterable[str],
    topic: str | None = None,
) -> Tuple[bool, str]:
    wrapper = root / "observability" / "tools" / "memory" / "save_now_wrapper.zsh"
    if not wrapper.exists():
        return False, f"save_now_wrapper_missing: {wrapper}"

    cmd = [
        "zsh",
        str(wrapper),
        "--agent-id",
        agent_id,
        "--trace-id",
        trace_id,
        "--phase",
        phase,
    ]
    if task_id:
        cmd.extend(["--task-id", task_id])
    if topic:
        cmd.extend(["--topic", topic])
    file_list = ",".join(files)
    if file_list:
        cmd.extend(["--files", file_list])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        if not err:
            err = f"save_now_failed_rc_{result.returncode}"
        return False, err
    return True, ""


def update_handoff(root: Path, meta: Dict[str, Any], summary: str) -> None:
    artifacts_dir = root / "observability" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    handoff_json = artifacts_dir / "handoff_latest.json"
    handoff_md = artifacts_dir / "handoff_latest.md"

    payload = {
        "ts": now_utc_iso(),
        "trace_id": meta.get("trace_id", ""),
        "status": meta.get("status", ""),
        "owner_agent_id": meta.get("agent_id_owner", ""),
        "summary_1line": summary,
        "paths": meta.get("paths", {}),
    }
    write_json(handoff_json, payload)

    lines = [
        "# Handoff Latest",
        "",
        f"Trace: {payload['trace_id']}",
        f"Status: {payload['status']}",
        f"Owner: {payload['owner_agent_id']}",
        f"Summary: {payload['summary_1line']}",
        "",
    ]
    paths = payload.get("paths", {})
    if paths:
        lines.append("Paths:")
        for key, value in paths.items():
            lines.append(f"- {key}: {value}")
    write_text(handoff_md, "\n".join(lines).strip() + "\n")


def write_plan_artifacts(
    root: Path,
    *,
    trace_id: str,
    task_id: str | None,
    agent_id: str,
    goal: str,
    plan: Dict[str, Any],
    plan_md: Optional[str] = None,
) -> Dict[str, Any]:
    work_dir = task_dir(root, trace_id)
    plan_json = work_dir / "plan.json"
    plan_md_path = work_dir / "plan.md"
    meta_path = work_dir / "meta.json"

    write_json(plan_json, plan)
    if plan_md is None:
        plan_md = build_plan_md(plan)
    write_text(plan_md_path, plan_md)

    meta = update_meta(
        meta_path,
        trace_id=trace_id,
        task_id=task_id,
        agent_id=agent_id,
        goal=goal,
        status="PLANNED",
        ts_key="ts_plan",
        paths={
            "plan_json": str(plan_json),
            "plan_md": str(plan_md_path),
            "meta": str(meta_path),
        },
    )

    ok, err = run_save_now(
        root,
        agent_id=agent_id,
        trace_id=trace_id,
        phase="plan",
        task_id=task_id,
        files=[str(plan_json), str(plan_md_path), str(meta_path)],
        topic=f"trace_id={trace_id} phase=plan task_id={task_id or ''}",
    )
    meta = update_save_now(meta, "OK" if ok else "FAIL", err if not ok else None)
    write_json(meta_path, meta)
    if not ok:
        log_save_now_failure(
            root,
            {
                "ts": now_utc_iso(),
                "trace_id": trace_id,
                "phase": "plan",
                "agent_id": agent_id,
                "task_id": task_id or "",
                "error": err,
            },
        )

    update_handoff(root, meta, goal)
    return meta


def write_result_artifacts(
    root: Path,
    *,
    trace_id: str,
    task_id: str | None,
    agent_id: str,
    goal: str | None,
    result_payload: Dict[str, Any],
    dashboard_result_path: str,
) -> Dict[str, Any]:
    work_dir = task_dir(root, trace_id)
    result_json = work_dir / "result.json"
    meta_path = work_dir / "meta.json"

    result_payload = dict(result_payload)
    result_payload.setdefault("trace_id", trace_id)
    result_payload["dashboard_result_path"] = dashboard_result_path
    write_json(result_json, result_payload)

    status = "DONE" if str(result_payload.get("status", "")).lower() == "ok" else "FAILED"
    meta = update_meta(
        meta_path,
        trace_id=trace_id,
        task_id=task_id,
        agent_id=agent_id,
        goal=goal,
        status=status,
        ts_key="ts_done",
        paths={
            "result_json": str(result_json),
            "meta": str(meta_path),
        },
    )

    ok, err = run_save_now(
        root,
        agent_id=agent_id,
        trace_id=trace_id,
        phase="done",
        task_id=task_id,
        files=[str(result_json), str(meta_path)],
        topic=f"trace_id={trace_id} phase=done task_id={task_id or ''}",
    )
    meta = update_save_now(meta, "OK" if ok else "FAIL", err if not ok else None)
    write_json(meta_path, meta)
    if not ok:
        log_save_now_failure(
            root,
            {
                "ts": now_utc_iso(),
                "trace_id": trace_id,
                "phase": "done",
                "agent_id": agent_id,
                "task_id": task_id or "",
                "error": err,
            },
        )

    summary = str(result_payload.get("summary") or "")
    if summary:
        update_handoff(root, meta, summary)
    return meta


def build_reply_md(status: str, summary: str, task_id: str | None) -> str:
    status_line = status or "unknown"
    lines = ["# Reply", "", f"Status: {status_line}", f"Summary: {summary}"]
    if task_id:
        lines.append(f"Task ID: {task_id}")
    return "\n".join(lines).strip() + "\n"


def write_reply_artifacts(
    root: Path,
    *,
    trace_id: str,
    task_id: str | None,
    agent_id: str,
    status: str,
    summary: str,
) -> Dict[str, Any]:
    work_dir = task_dir(root, trace_id)
    reply_md = work_dir / "reply.md"
    meta_path = work_dir / "meta.json"

    write_text(reply_md, build_reply_md(status, summary, task_id))

    meta = update_meta(
        meta_path,
        trace_id=trace_id,
        task_id=task_id,
        agent_id=agent_id,
        goal=None,
        status="REPLIED",
        ts_key="ts_reply",
        paths={
            "reply_md": str(reply_md),
            "meta": str(meta_path),
        },
    )

    ok, err = run_save_now(
        root,
        agent_id=agent_id,
        trace_id=trace_id,
        phase="reply",
        task_id=task_id,
        files=[str(reply_md), str(meta_path)],
        topic=f"trace_id={trace_id} phase=reply task_id={task_id or ''}",
    )
    meta = update_save_now(meta, "OK" if ok else "FAIL", err if not ok else None)
    write_json(meta_path, meta)
    if not ok:
        log_save_now_failure(
            root,
            {
                "ts": now_utc_iso(),
                "trace_id": trace_id,
                "phase": "reply",
                "agent_id": agent_id,
                "task_id": task_id or "",
                "error": err,
            },
        )

    update_handoff(root, meta, summary)
    return meta
