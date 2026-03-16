"""AG-56: Autonomous Supervision Dashboard API handlers.

Read endpoints (no operator_id required):
  GET  /api/supervision_dashboard/latest  — latest dashboard report
  GET  /api/supervision_dashboard/index   — slim dashboard index
  GET  /api/supervision_dashboard/alerts  — governance alerts section
  GET  /api/supervision_dashboard/trust   — trust index section
  GET  /api/supervision_dashboard/queue   — open decision queue summary

Write endpoint (operator_id required, 403 without):
  POST /api/supervision_dashboard/run     — trigger dashboard refresh

AG-56 invariant: dashboard-only. No mutation, no enforcement,
no auto-action, no repair execution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

from runtime.dashboard_policy import DASHBOARD_SECTIONS


def _load_json(filename: str, runtime_root: str | None = None) -> Any:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        return None
    path = Path(rt) / "state" / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


async def supervision_dashboard_latest() -> dict[str, Any]:
    """GET /api/supervision_dashboard/latest — latest dashboard report."""
    try:
        data = _load_json("runtime_supervision_dashboard_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def supervision_dashboard_index() -> dict[str, Any]:
    """GET /api/supervision_dashboard/index — slim dashboard index."""
    try:
        data = _load_json("runtime_supervision_dashboard_index.json")
        if data is None:
            return {
                "ok": True, "alert_count": 0, "high_alert_count": 0,
                "severity_counts": {}, "sections": DASHBOARD_SECTIONS,
            }
        return {
            "ok":               True,
            "alert_count":      data.get("alert_count", 0),
            "high_alert_count": data.get("high_alert_count", 0),
            "severity_counts":  data.get("severity_counts", {}),
            "sections":         data.get("sections", DASHBOARD_SECTIONS),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def supervision_dashboard_alerts() -> dict[str, Any]:
    """GET /api/supervision_dashboard/alerts — governance alerts section."""
    try:
        data = _load_json("runtime_supervision_dashboard_latest.json")
        if data is None:
            return {"ok": True, "governance_alerts": [], "alert_count": 0}
        return {
            "ok":               True,
            "governance_alerts": data.get("governance_alerts", []),
            "alert_count":      data.get("alert_count", 0),
            "high_alert_count": data.get("high_alert_count", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def supervision_dashboard_trust() -> dict[str, Any]:
    """GET /api/supervision_dashboard/trust — trust index section."""
    try:
        data = _load_json("runtime_supervision_dashboard_latest.json")
        if data is None:
            return {"ok": True, "trust_index": {}, "top_trust_gaps": []}
        return {
            "ok":            True,
            "trust_index":   data.get("trust_index", {}),
            "top_trust_gaps": data.get("top_trust_gaps", []),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def supervision_dashboard_queue() -> dict[str, Any]:
    """GET /api/supervision_dashboard/queue — open decision queue summary."""
    try:
        data = _load_json("runtime_supervision_dashboard_latest.json")
        if data is None:
            return {"ok": True, "open_decision_queue_summary": {}, "integrity_breaks": []}
        return {
            "ok":                         True,
            "open_decision_queue_summary": data.get("open_decision_queue_summary", {}),
            "integrity_breaks":           data.get("integrity_breaks", []),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def supervision_dashboard_run(request: "Request") -> "JSONResponse":
    """POST /api/supervision_dashboard/run — trigger dashboard refresh."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    try:
        from runtime.supervision_dashboard import run_supervision_dashboard
        result = run_supervision_dashboard()
        return JSONResponse(status_code=200, content={
            "ok":               True,
            "triggered_by":     operator_id,
            "alert_count":      result.get("alert_count", 0),
            "high_alert_count": result.get("high_alert_count", 0),
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"dashboard run failed: {exc}"})


def register_supervision_dashboard_routes(app: Any) -> None:
    """Register AG-56 routes on a FastAPI app instance."""
    app.add_api_route("/api/supervision_dashboard/latest",  supervision_dashboard_latest,  methods=["GET"])
    app.add_api_route("/api/supervision_dashboard/index",   supervision_dashboard_index,   methods=["GET"])
    app.add_api_route("/api/supervision_dashboard/alerts",  supervision_dashboard_alerts,  methods=["GET"])
    app.add_api_route("/api/supervision_dashboard/trust",   supervision_dashboard_trust,   methods=["GET"])
    app.add_api_route("/api/supervision_dashboard/queue",   supervision_dashboard_queue,   methods=["GET"])
    app.add_api_route("/api/supervision_dashboard/run",     supervision_dashboard_run,     methods=["POST"])
