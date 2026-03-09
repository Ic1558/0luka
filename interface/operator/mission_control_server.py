#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path
from string import Template
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    from starlette.applications import Starlette as FastAPI
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, JSONResponse
    FASTAPI_AVAILABLE = False

from starlette.routing import Route

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import approval_presets, approval_write, remediation_queue

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
CANONICAL_OBSERVABILITY_ROOT = Path("/Users/icmini/0luka/observability")
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7010
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "mission_control.html"


def _observability_root() -> Path:
    raw = os.environ.get("LUKA_OBSERVABILITY_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_OBSERVABILITY_ROOT


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _activity_feed_path() -> Path:
    return _observability_root() / "logs" / "activity_feed.jsonl"


def _alerts_path() -> Path:
    return _runtime_root() / "state" / "alerts.jsonl"


def _approval_actions_path() -> Path:
    return _runtime_root() / "state" / "approval_actions.jsonl"


def _approval_log_path() -> Path:
    primary = _runtime_root() / "state" / "approval_log.jsonl"
    if primary.exists():
        return primary
    return _approval_actions_path()


def _remediation_history_log_path() -> Path:
    return _runtime_root() / "state" / "remediation_history.jsonl"


def _qs_runs_dir() -> Path:
    return _runtime_root() / "state" / "qs_runs"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{path}")
    return payload


def _run_json_command(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    stream = proc.stdout.strip() or proc.stderr.strip()
    if not stream:
        raise RuntimeError(f"empty_output:{' '.join(args)}")
    payload = json.loads(stream)
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{' '.join(args)}")
    return payload


def load_operator_status() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/operator_status_report.py", "--json"])


def load_runtime_status() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/runtime_status_report.py", "--json"])


def load_activity_entries(limit: int = 50) -> list[dict[str, Any]]:
    path = _activity_feed_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def load_alerts(limit: int = 100) -> list[dict[str, Any]]:
    path = _alerts_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def load_approval_history(lane: str | None = None, last: int | None = None) -> dict[str, Any]:
    path = _approval_actions_path()
    rows: list[dict[str, Any]] = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            lane_name = str(row.get("lane") or "")
            if lane and lane_name != lane:
                continue
            rows.append(
                {
                    "timestamp": row.get("timestamp"),
                    "lane": lane_name or None,
                    "action": row.get("action"),
                    "actor": row.get("actor"),
                    "approved": bool(row.get("approved", False)),
                    "expires_at": row.get("expires_at"),
                    "source": row.get("source", "approval_write"),
                }
            )
    if last is not None and last >= 0:
        rows = rows[-last:]
    return {
        "events": rows,
        "last_event": rows[-1] if rows else None,
        "total_entries": len(rows),
    }


def _read_jsonl_entries(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def load_remediation_audit_entries(last: int = 100) -> dict[str, Any]:
    rows = _read_jsonl_entries(_remediation_history_log_path())
    if last >= 0:
        rows = rows[-last:]
    return {"ok": True, "entries": rows}


def load_approval_log_entries(last: int = 100) -> dict[str, Any]:
    rows = _read_jsonl_entries(_approval_log_path())
    if last >= 0:
        rows = rows[-last:]
    return {"ok": True, "entries": rows}


def load_runtime_decisions(last: int = 100) -> dict[str, Any]:
    rows = []
    for entry in _read_jsonl_entries(_remediation_history_log_path()):
        if "decision" not in entry:
            continue
        rows.append(entry)
    if last >= 0:
        rows = rows[-last:]
    return {"ok": True, "entries": rows}


def _normalize_qs_run_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": str(row.get("run_id") or ""),
        "job_type": str(row.get("job_type") or ""),
        "project_id": str(row.get("project_id") or ""),
        "qs_status": str(row.get("qs_status") or ""),
        "requires_approval": bool(row.get("requires_approval", False)),
        "approval_state": row.get("approval_state"),
        "runtime_state": row.get("runtime_state"),
        "execution_status": row.get("execution_status"),
        "block_reason": row.get("block_reason"),
        "approved_by": row.get("approved_by"),
        "approved_at": row.get("approved_at"),
        "approval_reason": row.get("approval_reason"),
        "artifacts": row.get("artifacts") if isinstance(row.get("artifacts"), list) else [],
    }


def load_qs_run(run_id: str) -> dict[str, Any]:
    path = _qs_runs_dir() / f"{str(run_id or '').strip()}.json"
    if not path.exists():
        raise RuntimeError(f"qs_run_not_found:{run_id}")
    payload = _read_json(path)
    projection = _normalize_qs_run_projection(payload)
    if not projection["run_id"]:
        raise RuntimeError(f"qs_run_invalid:{run_id}")
    return {"ok": True, "run": projection}


def load_qs_runs_summary() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for path in sorted(_qs_runs_dir().glob("*.json")):
        try:
            payload = _read_json(path)
            projection = _normalize_qs_run_projection(payload)
        except Exception:
            continue
        if not projection["run_id"]:
            continue
        items.append(projection)

    summary = {
        "total_runs": len(items),
        "blocked_runs": sum(1 for item in items if str(item.get("execution_status") or "") == "blocked"),
        "allowed_runs": sum(1 for item in items if str(item.get("execution_status") or "") == "allowed"),
        "pending_approval_runs": sum(1 for item in items if str(item.get("approval_state") or "") == "pending_approval"),
        "approved_runs": sum(1 for item in items if str(item.get("approval_state") or "") == "approved"),
        "not_required_runs": sum(1 for item in items if str(item.get("approval_state") or "") == "not_required"),
    }
    return {"ok": True, "items": items, "summary": summary}


def _build_remediation_timeline(report: dict[str, Any], *, last: int | None = None) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for lane_name in ("memory", "worker"):
        lane_payload = report.get(lane_name)
        if not isinstance(lane_payload, dict):
            continue
        for decision in lane_payload.get("lifecycle", []):
            timeline.append(
                {
                    "timestamp": None,
                    "decision": str(decision),
                    "lane": lane_name,
                }
            )
    if last is not None and last >= 0:
        timeline = timeline[-last:]
    return timeline


def load_remediation_history(lane: str | None = None, last: int | None = None) -> dict[str, Any]:
    args = [sys.executable, "tools/ops/remediation_history_report.py", "--json"]
    if lane:
        args.extend(["--lane", lane])
    if last is not None:
        args.extend(["--last", str(last)])
    payload = _run_json_command(args)
    payload["timeline"] = _build_remediation_timeline(payload, last=last)
    payload.setdefault("last_event", {"decision": None, "lane": None, "timestamp": None})
    payload.setdefault("total_entries", 0)
    for lane_name in ("memory", "worker"):
        if lane and lane_name != lane:
            continue
        if lane_name not in payload:
            payload[lane_name] = {
                "attempts": 0,
                "cooldowns": 0,
                "escalations": 0,
                "recovered": 0,
                "lifecycle": [],
            }
    return payload


def load_autonomy_policy(lane: str | None = None) -> dict[str, Any]:
    args = [sys.executable, "tools/ops/autonomy_policy.py", "--json"]
    if lane:
        args.extend(["--lane", lane])
    return _run_json_command(args)


def apply_approval_action(
    *,
    lane: str,
    actor: str,
    approve: bool = False,
    revoke: bool = False,
    expires_at: str | None = None,
    clear_expiry: bool = False,
) -> dict[str, Any]:
    return approval_write.write_approval_action(
        lane=lane,
        actor=actor,
        approve=approve,
        revoke=revoke,
        expires_at=expires_at,
        clear_expiry=clear_expiry,
    )

def load_approval_presets() -> dict[str, Any]:
    return approval_presets.list_presets(runtime_root=_runtime_root())


def load_approval_expiry() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/approval_expiry_monitor.py", "--json"])


def load_policy_drift() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/policy_drift_detector.py", "--json"])


def load_remediation_queue() -> dict[str, Any]:
    return remediation_queue.list_queue(runtime_root=_runtime_root())


def enqueue_remediation_queue(*, lane: str, action: str) -> dict[str, Any]:
    return remediation_queue.enqueue_item(lane=lane, action=action, runtime_root=_runtime_root())


def apply_approval_preset(*, preset: str) -> dict[str, Any]:
    return approval_presets.apply_preset(preset=preset, runtime_root=_runtime_root())


def reset_approval_preset(*, preset: str) -> dict[str, Any]:
    return approval_presets.reset_preset(preset=preset, runtime_root=_runtime_root())


def _epoch_id(runtime_status: dict[str, Any]) -> str:
    proof = runtime_status.get("proof_pack")
    if isinstance(proof, dict):
        epoch = proof.get("epoch_id")
        if epoch is not None:
            return str(epoch)
    return "n/a"


def _activity_html(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "<li>No activity available</li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        ts = escape(str(row.get("ts_utc") or row.get("ts") or "n/a"))
        action = escape(str(row.get("action") or row.get("event") or "unknown"))
        items.append(f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span></li>")
    return "\n".join(items)


def _alerts_html(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "<li class=\"alert-item info\"><span class=\"severity\">INFO</span><span class=\"component\">alerts</span><span class=\"message\">No alerts available</span></li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        severity = escape(str(row.get("severity") or "INFO")).lower()
        ts = escape(str(row.get("timestamp") or "n/a"))
        component = escape(str(row.get("component") or "unknown"))
        message = escape(str(row.get("message") or ""))
        items.append(
            "<li class=\"alert-item {severity}\">"
            "<span class=\"ts\">{ts}</span>"
            "<span class=\"severity\">{sev}</span>"
            "<span class=\"component\">{component}</span>"
            "<span class=\"message\">{message}</span>"
            "</li>".format(
                severity=severity,
                ts=ts,
                sev=escape(str(row.get("severity") or "INFO")),
                component=component,
                message=message,
            )
        )
    return "\n".join(items)


def _remediation_summary_html(report: dict[str, Any]) -> str:
    blocks: list[str] = []
    for lane_name in ("memory", "worker"):
        lane_payload = report.get(lane_name)
        if not isinstance(lane_payload, dict):
            continue
        blocks.append(
            "<div class=\"lane-block\">"
            f"<h3>{escape(lane_name.title())}</h3>"
            "<dl>"
            f"<dt>Attempts</dt><dd>{escape(str(lane_payload.get('attempts', 0)))}</dd>"
            f"<dt>Cooldowns</dt><dd>{escape(str(lane_payload.get('cooldowns', 0)))}</dd>"
            f"<dt>Escalations</dt><dd>{escape(str(lane_payload.get('escalations', 0)))}</dd>"
            f"<dt>Recovered</dt><dd>{escape(str(lane_payload.get('recovered', 0)))}</dd>"
            "</dl>"
            "</div>"
        )
    if not blocks:
        return "<p class=\"muted\">No remediation history available</p>"
    return "\n".join(blocks)


def _remediation_last_event_html(report: dict[str, Any]) -> str:
    event = report.get("last_event")
    if not isinstance(event, dict):
        event = {}
    return (
        "<dl>"
        f"<dt>Decision</dt><dd>{escape(str(event.get('decision') or 'n/a'))}</dd>"
        f"<dt>Lane</dt><dd>{escape(str(event.get('lane') or 'n/a'))}</dd>"
        f"<dt>Timestamp</dt><dd>{escape(str(event.get('timestamp') or 'n/a'))}</dd>"
        "</dl>"
    )


def _remediation_timeline_html(report: dict[str, Any]) -> str:
    entries = report.get("timeline")
    if not isinstance(entries, list) or not entries:
        return "<li>No remediation events available</li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        if not isinstance(row, dict):
            continue
        ts = escape(str(row.get("timestamp") or "n/a"))
        decision = escape(str(row.get("decision") or "unknown"))
        lane = escape(str(row.get("lane") or "unknown"))
        items.append(
            f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{decision}</span> <span class=\"lane\">({lane})</span></li>"
        )
    return "\n".join(items) if items else "<li>No remediation events available</li>"


def _approval_history_last_event_html(payload: dict[str, Any]) -> str:
    event = payload.get("last_event")
    if not isinstance(event, dict):
        event = {}
    return (
        "<dl>"
        f"<dt>Action</dt><dd>{escape(str(event.get('action') or 'n/a'))}</dd>"
        f"<dt>Lane</dt><dd>{escape(str(event.get('lane') or 'n/a'))}</dd>"
        f"<dt>Actor</dt><dd>{escape(str(event.get('actor') or 'n/a'))}</dd>"
        f"<dt>Timestamp</dt><dd>{escape(str(event.get('timestamp') or 'n/a'))}</dd>"
        "</dl>"
    )


def _approval_history_timeline_html(payload: dict[str, Any]) -> str:
    entries = payload.get("events")
    if not isinstance(entries, list) or not entries:
        return "<li>No approval history available</li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        if not isinstance(row, dict):
            continue
        ts = escape(str(row.get("timestamp") or "n/a"))
        action = escape(str(row.get("action") or "unknown"))
        lane = escape(str(row.get("lane") or "unknown"))
        actor = escape(str(row.get("actor") or "n/a"))
        expires = escape(str(row.get("expires_at") or "n/a"))
        items.append(
            f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span> "
            f"<span class=\"lane\">({lane})</span> <span class=\"actor\">by {actor}</span> "
            f"<span class=\"expiry\">expires={expires}</span></li>"
        )
    return "\n".join(items) if items else "<li>No approval history available</li>"


def _autonomy_policy_html(payload: dict[str, Any]) -> str:
    lanes = payload.get("lanes")
    if not isinstance(lanes, dict) or not lanes:
        return "<li>No autonomy policy available</li>"
    items: list[str] = []
    for lane_name in ("memory_recovery", "worker_recovery", "api_recovery", "redis_recovery"):
        row = lanes.get(lane_name)
        if not isinstance(row, dict):
            continue
        items.append(
            "<li class=\"policy-item status-{status}\">"
            "<span class=\"lane-name\">{lane}</span>"
            "<span class=\"policy-status\">{state}</span>"
            "<span class=\"policy-reason\">{reason}</span>"
            "<span class=\"policy-meta\">approval={approval}; expires={expires}; expired={expired}; expiring_soon={expiring}</span>"
            "<div class=\"policy-controls\">"
            "<input class=\"policy-actor\" data-lane=\"{lane_raw}\" placeholder=\"actor\">"
            "<input class=\"policy-expiry\" data-lane=\"{lane_raw}\" placeholder=\"expires_at (UTC)\">"
            "<button type=\"button\" onclick=\"submitApprovalAction('approve','{lane_raw}')\">Approve</button>"
            "<button type=\"button\" onclick=\"submitApprovalAction('revoke','{lane_raw}')\">Revoke</button>"
            "<button type=\"button\" onclick=\"submitApprovalExpiry('{lane_raw}', false)\">Set Expiry</button>"
            "<button type=\"button\" onclick=\"submitApprovalExpiry('{lane_raw}', true)\">Clear Expiry</button>"
            "</div>"
            "</li>".format(
                lane=escape(lane_name),
                lane_raw=escape(lane_name),
                status=escape(str(row.get("status", "denied")).lower()),
                state=escape(str(row.get("status", "denied"))),
                reason=escape(str(row.get("reason", "unknown"))),
                approval=escape(str(row.get("approval_state", "invalid"))),
                expires=escape(str(row.get("expires_at") or "n/a")),
                expired=escape(str(bool(row.get("expired"))).lower()),
                expiring=escape(str(bool(row.get("expiring_soon"))).lower()),
            )
        )
    return "\n".join(items) if items else "<li>No autonomy policy available</li>"


def _approval_presets_html(payload: dict[str, Any]) -> str:
    presets = payload.get("presets")
    if not isinstance(presets, list) or not presets:
        return "<li>No approval presets available</li>"
    items: list[str] = []
    for row in presets:
        if not isinstance(row, dict):
            continue
        name = escape(str(row.get("name") or "unknown"))
        lanes = row.get("lanes")
        lanes_text = ", ".join(str(x) for x in lanes) if isinstance(lanes, list) and lanes else "none"
        last_applied_at = escape(str(row.get("last_applied_at") or "n/a"))
        items.append(
            "<li class=\"policy-item\">"
            f"<span class=\"lane-name\">{name}</span>"
            f"<span class=\"policy-meta\">lanes={escape(lanes_text)}; last_applied={last_applied_at}</span>"
            "<div class=\"policy-controls\">"
            f"<button type=\"button\" onclick=\"submitPresetAction('apply','{name}')\">Apply</button>"
            f"<button type=\"button\" onclick=\"submitPresetAction('reset','{name}')\">Reset</button>"
            "</div>"
            "</li>"
        )
    return "\n".join(items) if items else "<li>No approval presets available</li>"


def _approval_expiry_html(payload: dict[str, Any]) -> str:
    lanes = payload.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        return "<li>No approval expiry data available</li>"
    rows: list[str] = []
    for row in lanes:
        if not isinstance(row, dict):
            continue
        lane = escape(str(row.get("lane") or "unknown"))
        status = escape(str(row.get("status") or "OK"))
        actor = escape(str(row.get("actor") or "n/a"))
        expires_at = escape(str(row.get("expires_at") or "n/a"))
        rows.append(
            f"<li class=\"policy-item status-{status.lower()}\">"
            f"<span class=\"lane-name\">{lane}</span>"
            f"<span class=\"policy-status\">{status}</span>"
            f"<span class=\"policy-meta\">actor={actor}; expires_at={expires_at}</span>"
            "</li>"
        )
    return "\n".join(rows) if rows else "<li>No approval expiry data available</li>"


def _policy_drift_html(payload: dict[str, Any]) -> str:
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        return "<li>No policy drift data available</li>"
    rows: list[str] = []
    for key in (
        "approval_log_consistency",
        "expiry_consistency",
        "env_gate_consistency",
        "lane_registry_consistency",
    ):
        status = str(checks.get(key, "UNKNOWN"))
        rows.append(
            f"<li class=\"policy-item status-{escape(status.lower())}\">"
            f"<span class=\"lane-name\">{escape(key)}</span>"
            f"<span class=\"policy-status\">{escape(status)}</span>"
            "</li>"
        )
    return "\n".join(rows) if rows else "<li>No policy drift data available</li>"


def _remediation_queue_html(payload: dict[str, Any]) -> str:
    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        return "<li>No remediation queue items</li>"
    items: list[str] = []
    for row in reversed(rows[-10:]):
        if not isinstance(row, dict):
            continue
        items.append(
            "<li class=\"policy-item status-{state}\">"
            "<span class=\"lane-name\">{item_id}</span>"
            "<span class=\"policy-status\">{state}</span>"
            "<span class=\"policy-meta\">lane={lane}; action={action}; attempts={attempts}; created_at={created_at}</span>"
            "</li>".format(
                item_id=escape(str(row.get("id") or "n/a")),
                state=escape(str(row.get("state") or "queued")).lower(),
                lane=escape(str(row.get("lane") or "unknown")),
                action=escape(str(row.get("action") or "unknown")),
                attempts=escape(str(row.get("attempts", 0))),
                created_at=escape(str(row.get("created_at") or "n/a")),
            )
        )
    return "\n".join(items) if items else "<li>No remediation queue items</li>"


def _audit_entries_html(payload: dict[str, Any], *, kind: str) -> str:
    rows = payload.get("entries")
    if not isinstance(rows, list) or not rows:
        return "<li>No entries available</li>"
    items: list[str] = []
    for row in reversed(rows[-10:]):
        if not isinstance(row, dict):
            continue
        ts = escape(str(row.get("timestamp") or "n/a"))
        lane = escape(str(row.get("lane") or "n/a"))
        action = escape(str(row.get("action") or row.get("decision") or "unknown"))
        actor = escape(str(row.get("actor") or "n/a"))
        result = escape(str(row.get("result") or "n/a"))
        if kind == "runtime_decisions":
            items.append(
                f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span> <span class=\"lane\">({lane})</span> <span class=\"result\">result={result}</span></li>"
            )
        elif kind == "approval_log":
            items.append(
                f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span> <span class=\"lane\">({lane})</span> <span class=\"actor\">by {actor}</span></li>"
            )
        else:
            items.append(
                f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span> <span class=\"lane\">({lane})</span> <span class=\"result\">result={result}</span></li>"
            )
    return "\n".join(items) if items else "<li>No entries available</li>"


def render_mission_control(
    operator_status: dict[str, Any],
    runtime_status: dict[str, Any],
    activity_entries: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    remediation_history: dict[str, Any],
    autonomy_policy: dict[str, Any],
    approval_history: dict[str, Any],
    approval_presets_payload: dict[str, Any],
    approval_expiry_payload: dict[str, Any],
    policy_drift_payload: dict[str, Any],
    remediation_queue_payload: dict[str, Any],
    remediation_audit_payload: dict[str, Any],
    approval_log_payload: dict[str, Any],
    runtime_decisions_payload: dict[str, Any],
) -> str:
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    details = operator_status.get("details") if isinstance(operator_status.get("details"), dict) else {}
    bridge = details.get("bridge_checks") if isinstance(details.get("bridge_checks"), dict) else {}
    return template.safe_substitute(
        system_health=escape(str(runtime_status.get("system_health", {}).get("status", "FAILED"))),
        ledger_status=escape(str(operator_status.get("ledger_status", "FAILED"))),
        epoch_id=escape(_epoch_id(runtime_status)),
        operator_overall=escape(str(operator_status.get("overall_status", "UNKNOWN"))),
        memory_status=escape(str(operator_status.get("memory_status", "UNAVAILABLE"))),
        api_server=escape(str(operator_status.get("api_server", "MISSING"))),
        redis=escape(str(operator_status.get("redis", "MISSING"))),
        bridge_consumer=escape(str(bridge.get("consumer", "unavailable"))),
        bridge_inflight=escape(str(bridge.get("inflight", "unavailable"))),
        bridge_outbox=escape(str(bridge.get("outbox", "unavailable"))),
        activity_items=_activity_html(activity_entries),
        alert_items=_alerts_html(alerts),
        remediation_summary=_remediation_summary_html(remediation_history),
        remediation_last_event=_remediation_last_event_html(remediation_history),
        remediation_timeline=_remediation_timeline_html(remediation_history),
        autonomy_policy_items=_autonomy_policy_html(autonomy_policy),
        approval_history_last_event=_approval_history_last_event_html(approval_history),
        approval_history_timeline=_approval_history_timeline_html(approval_history),
        approval_presets_items=_approval_presets_html(approval_presets_payload),
        approval_expiry_items=_approval_expiry_html(approval_expiry_payload),
        policy_drift_items=_policy_drift_html(policy_drift_payload),
        remediation_queue_items=_remediation_queue_html(remediation_queue_payload),
        remediation_audit_items=_audit_entries_html(remediation_audit_payload, kind="remediation_history"),
        approval_log_items=_audit_entries_html(approval_log_payload, kind="approval_log"),
        runtime_decision_items=_audit_entries_html(runtime_decisions_payload, kind="runtime_decisions"),
    )


async def health_endpoint(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "mission_control", "port": SERVER_PORT})


async def operator_status_endpoint(request) -> JSONResponse:
    return JSONResponse(load_operator_status())


async def runtime_status_endpoint(request) -> JSONResponse:
    return JSONResponse(load_runtime_status())


async def activity_endpoint(request) -> JSONResponse:
    return JSONResponse(load_activity_entries())


async def alerts_endpoint(request) -> JSONResponse:
    limit_raw = request.query_params.get("limit", "100")
    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 100
    return JSONResponse({"alerts": load_alerts(limit=limit)})


async def remediation_history_endpoint(request) -> JSONResponse:
    lane = request.query_params.get("lane")
    if lane not in {None, "", "memory", "worker"}:
        lane = None
    last_raw = request.query_params.get("last")
    last = 100
    if last_raw:
        try:
            last = max(0, min(int(last_raw), 500))
        except ValueError:
            last = 100
    payload = load_remediation_audit_entries(last=last)
    # Preserve existing summary payload shape for backward compatibility.
    payload.update(load_remediation_history(lane=lane or None, last=last))
    return JSONResponse(payload)


async def autonomy_policy_endpoint(request) -> JSONResponse:
    lane = request.query_params.get("lane")
    if lane not in {None, "", "memory_recovery", "worker_recovery", "api_recovery", "redis_recovery"}:
        lane = None
    return JSONResponse(load_autonomy_policy(lane=lane or None))


async def approval_history_endpoint(request) -> JSONResponse:
    lane = request.query_params.get("lane")
    if lane not in {None, "", "memory_recovery", "worker_recovery", "api_recovery", "redis_recovery"}:
        lane = None
    last_raw = request.query_params.get("last")
    last: int | None = None
    if last_raw:
        try:
            last = max(0, min(int(last_raw), 500))
        except ValueError:
            last = None
    return JSONResponse(load_approval_history(lane=lane or None, last=last))


async def approval_log_endpoint(request) -> JSONResponse:
    last_raw = request.query_params.get("last")
    last = 100
    if last_raw:
        try:
            last = max(0, min(int(last_raw), 500))
        except ValueError:
            last = 100
    return JSONResponse(load_approval_log_entries(last=last))


async def runtime_decisions_endpoint(request) -> JSONResponse:
    last_raw = request.query_params.get("last")
    last = 100
    if last_raw:
        try:
            last = max(0, min(int(last_raw), 500))
        except ValueError:
            last = 100
    return JSONResponse(load_runtime_decisions(last=last))


async def qs_runs_endpoint(request: Request) -> JSONResponse:
    return JSONResponse(load_qs_runs_summary())


async def qs_run_endpoint(request: Request) -> JSONResponse:
    run_id = str(request.path_params.get("run_id") or "").strip()
    if not run_id:
        return JSONResponse({"ok": False, "error": "missing_run_id"}, status_code=400)
    try:
        return JSONResponse(load_qs_run(run_id))
    except RuntimeError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)

async def approval_presets_endpoint(request) -> JSONResponse:
    return JSONResponse(load_approval_presets())


async def approval_expiry_status_endpoint(request) -> JSONResponse:
    return JSONResponse(load_approval_expiry())


async def policy_drift_endpoint(request) -> JSONResponse:
    return JSONResponse(load_policy_drift())


async def remediation_queue_endpoint(request) -> JSONResponse:
    return JSONResponse(load_remediation_queue())


async def remediation_queue_enqueue_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        lane = str(payload.get("lane", "")).strip()
        action = str(payload.get("action", "")).strip()
        result = enqueue_remediation_queue(lane=lane, action=action)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def _request_json(request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise RuntimeError("invalid_json_body")
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_json_body")
    return payload


async def approval_approve_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        result = apply_approval_action(
            lane=str(payload.get("lane", "")),
            actor=str(payload.get("actor", "")),
            approve=True,
            expires_at=payload.get("expires_at"),
        )
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def approval_revoke_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        result = apply_approval_action(
            lane=str(payload.get("lane", "")),
            actor=str(payload.get("actor", "")),
            revoke=True,
        )
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def approval_expiry_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        result = apply_approval_action(
            lane=str(payload.get("lane", "")),
            actor=str(payload.get("actor", "")),
            expires_at=payload.get("expires_at"),
            clear_expiry=bool(payload.get("clear_expiry")),
        )
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)

async def approval_presets_apply_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        preset = str(payload.get("preset", "")).strip()
        result = apply_approval_preset(preset=preset)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def approval_presets_reset_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        preset = str(payload.get("preset", "")).strip()
        result = reset_approval_preset(preset=preset)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def root_endpoint(request) -> HTMLResponse:
    operator_status = load_operator_status()
    runtime_status = load_runtime_status()
    activity_entries = load_activity_entries()
    alerts = load_alerts()
    remediation_history = load_remediation_history(last=20)
    autonomy_policy = load_autonomy_policy()
    approval_history = load_approval_history(last=20)
    approval_presets_payload = load_approval_presets()
    approval_expiry_payload = load_approval_expiry()
    policy_drift_payload = load_policy_drift()
    remediation_queue_payload = load_remediation_queue()
    remediation_audit_payload = load_remediation_audit_entries(last=20)
    approval_log_payload = load_approval_log_entries(last=20)
    runtime_decisions_payload = load_runtime_decisions(last=20)
    return HTMLResponse(
        render_mission_control(
            operator_status,
            runtime_status,
            activity_entries,
            alerts,
            remediation_history,
            autonomy_policy,
            approval_history,
            approval_presets_payload,
            approval_expiry_payload,
            policy_drift_payload,
            remediation_queue_payload,
            remediation_audit_payload,
            approval_log_payload,
            runtime_decisions_payload,
        )
    )


def create_app():
    if FASTAPI_AVAILABLE:
        app = FastAPI(title="0luka Mission Control", version="0.1.0")
        app.add_api_route("/health", health_endpoint, methods=["GET"])
        app.add_api_route("/api/operator_status", operator_status_endpoint, methods=["GET"])
        app.add_api_route("/api/runtime_status", runtime_status_endpoint, methods=["GET"])
        app.add_api_route("/api/activity", activity_endpoint, methods=["GET"])
        app.add_api_route("/api/alerts", alerts_endpoint, methods=["GET"])
        app.add_api_route("/api/remediation_history", remediation_history_endpoint, methods=["GET"])
        app.add_api_route("/api/autonomy_policy", autonomy_policy_endpoint, methods=["GET"])
        app.add_api_route("/api/approval_history", approval_history_endpoint, methods=["GET"])
        app.add_api_route("/api/approval_presets", approval_presets_endpoint, methods=["GET"])
        app.add_api_route("/api/approval_expiry", approval_expiry_status_endpoint, methods=["GET"])
        app.add_api_route("/api/policy_drift", policy_drift_endpoint, methods=["GET"])
        app.add_api_route("/api/approval_log", approval_log_endpoint, methods=["GET"])
        app.add_api_route("/api/runtime_decisions", runtime_decisions_endpoint, methods=["GET"])
        app.add_api_route("/api/qs_runs", qs_runs_endpoint, methods=["GET"])
        app.add_api_route("/api/qs_runs/{run_id}", qs_run_endpoint, methods=["GET"])
        app.add_api_route("/api/remediation_queue", remediation_queue_endpoint, methods=["GET"])
        app.add_api_route("/api/remediation_queue/enqueue", remediation_queue_enqueue_endpoint, methods=["POST"])
        app.add_api_route("/api/approval_presets/apply", approval_presets_apply_endpoint, methods=["POST"])
        app.add_api_route("/api/approval_presets/reset", approval_presets_reset_endpoint, methods=["POST"])
        app.add_api_route("/api/approval/approve", approval_approve_endpoint, methods=["POST"])
        app.add_api_route("/api/approval/revoke", approval_revoke_endpoint, methods=["POST"])
        app.add_api_route("/api/approval/expiry", approval_expiry_endpoint, methods=["POST"])
        app.add_api_route("/", root_endpoint, methods=["GET"], response_class=HTMLResponse)
        return app

    return FastAPI(
        routes=[
            Route("/health", health_endpoint),
            Route("/api/operator_status", operator_status_endpoint),
            Route("/api/runtime_status", runtime_status_endpoint),
            Route("/api/activity", activity_endpoint),
            Route("/api/alerts", alerts_endpoint),
            Route("/api/remediation_history", remediation_history_endpoint),
            Route("/api/autonomy_policy", autonomy_policy_endpoint),
            Route("/api/approval_history", approval_history_endpoint),
            Route("/api/approval_presets", approval_presets_endpoint),
            Route("/api/approval_expiry", approval_expiry_status_endpoint),
            Route("/api/policy_drift", policy_drift_endpoint),
            Route("/api/approval_log", approval_log_endpoint),
            Route("/api/runtime_decisions", runtime_decisions_endpoint),
            Route("/api/qs_runs", qs_runs_endpoint),
            Route("/api/qs_runs/{run_id}", qs_run_endpoint),
            Route("/api/remediation_queue", remediation_queue_endpoint),
            Route("/api/remediation_queue/enqueue", remediation_queue_enqueue_endpoint, methods=["POST"]),
            Route("/api/approval_presets/apply", approval_presets_apply_endpoint, methods=["POST"]),
            Route("/api/approval_presets/reset", approval_presets_reset_endpoint, methods=["POST"]),
            Route("/api/approval/approve", approval_approve_endpoint, methods=["POST"]),
            Route("/api/approval/revoke", approval_revoke_endpoint, methods=["POST"]),
            Route("/api/approval/expiry", approval_expiry_endpoint, methods=["POST"]),
            Route("/", root_endpoint),
        ]
    )


app = create_app()


def main() -> int:
    import uvicorn

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
