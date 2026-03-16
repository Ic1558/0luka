"""AG-55: Governance Alert System API handlers.

Read endpoints (no operator_id required):
  GET  /api/governance_alerts/latest   — latest alert report
  GET  /api/governance_alerts/index    — slim alert index
  GET  /api/governance_alerts/classes  — alert class list
  GET  /api/governance_alerts/high     — HIGH + CRITICAL alerts only

Write endpoint (operator_id required, 403 without):
  POST /api/governance_alerts/run      — trigger alert detection run

AG-55 invariant: alert-only. No mutation, no enforcement,
no auto-escalation, no repair execution.
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

from runtime.governance_alert_policy import ALERT_CLASSES


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


async def governance_alerts_latest() -> dict[str, Any]:
    """GET /api/governance_alerts/latest — latest alert report."""
    try:
        data = _load_json("runtime_governance_alerts_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def governance_alerts_index() -> dict[str, Any]:
    """GET /api/governance_alerts/index — slim alert index."""
    try:
        data = _load_json("runtime_governance_alerts_index.json")
        if data is None:
            return {
                "ok": True, "alert_count": 0, "high_alert_count": 0,
                "severity_counts": {"INFO": 0, "WARNING": 0, "HIGH": 0, "CRITICAL": 0},
            }
        return {
            "ok":               True,
            "alert_count":      data.get("alert_count", 0),
            "high_alert_count": data.get("high_alert_count", 0),
            "severity_counts":  data.get("severity_counts", {}),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def governance_alerts_classes() -> dict[str, Any]:
    """GET /api/governance_alerts/classes — alert class list."""
    try:
        return {"ok": True, "alert_classes": ALERT_CLASSES}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def governance_alerts_high() -> dict[str, Any]:
    """GET /api/governance_alerts/high — HIGH + CRITICAL alerts only."""
    try:
        data = _load_json("runtime_governance_alerts_latest.json")
        if data is None:
            return {"ok": True, "high_alerts": [], "high_alert_count": 0}
        high = data.get("high_alerts", [])
        return {"ok": True, "high_alerts": high, "high_alert_count": len(high)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def governance_alerts_run(request: "Request") -> "JSONResponse":
    """POST /api/governance_alerts/run — trigger alert detection run."""
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
        from runtime.governance_alerts import run_governance_alerts
        result = run_governance_alerts()
        return JSONResponse(status_code=200, content={
            "ok":               True,
            "triggered_by":     operator_id,
            "alert_count":      result.get("alert_count", 0),
            "high_alert_count": result.get("high_alert_count", 0),
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"alert run failed: {exc}"})


def register_governance_alerts_routes(app: Any) -> None:
    """Register AG-55 routes on a FastAPI app instance."""
    app.add_api_route("/api/governance_alerts/latest",  governance_alerts_latest,  methods=["GET"])
    app.add_api_route("/api/governance_alerts/index",   governance_alerts_index,   methods=["GET"])
    app.add_api_route("/api/governance_alerts/classes", governance_alerts_classes, methods=["GET"])
    app.add_api_route("/api/governance_alerts/high",    governance_alerts_high,    methods=["GET"])
    app.add_api_route("/api/governance_alerts/run",     governance_alerts_run,     methods=["POST"])
