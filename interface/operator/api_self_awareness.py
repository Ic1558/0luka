"""AG-47: Runtime Self-Awareness System API handlers.

Read endpoints (no operator_id required):
  GET  /api/self_awareness/latest        — latest self-awareness report
  GET  /api/self_awareness/readiness     — readiness summary
  GET  /api/self_awareness/posture       — runtime posture
  GET  /api/self_awareness/capabilities  — active capabilities list

Write endpoint (operator_id required, 403 without):
  POST /api/self_awareness/run           — trigger self-awareness synthesis

AG-47 invariant: descriptive-only. No governance mutation, no campaign
mutation, no repair execution, no baseline mutation, no capability
auto-activation.
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


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

async def self_awareness_latest() -> dict[str, Any]:
    """GET /api/self_awareness/latest — latest self-awareness report."""
    try:
        data = _load_json("runtime_self_awareness_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def self_awareness_readiness() -> dict[str, Any]:
    """GET /api/self_awareness/readiness — readiness summary."""
    try:
        data = _load_json("runtime_readiness.json")
        if data is None:
            return {
                "ok": True, "readiness": None, "confidence": 0.0,
                "reasons": [], "operating_mode": None, "critical_gaps": [],
            }
        return {
            "ok":            True,
            "readiness":     data.get("readiness"),
            "confidence":    data.get("confidence", 0.0),
            "reasons":       data.get("reasons", []),
            "operating_mode": data.get("operating_mode"),
            "critical_gaps": data.get("critical_gaps", []),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def self_awareness_posture() -> dict[str, Any]:
    """GET /api/self_awareness/posture — runtime posture."""
    try:
        data = _load_json("runtime_self_awareness_latest.json")
        if data is None:
            return {"ok": True, "posture": {}}
        return {"ok": True, "posture": data.get("posture", {})}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def self_awareness_capabilities() -> dict[str, Any]:
    """GET /api/self_awareness/capabilities — active capabilities list."""
    try:
        data = _load_json("runtime_self_awareness_latest.json")
        if data is None:
            return {"ok": True, "active_capabilities": [], "active_count": 0}
        identity = data.get("identity", {})
        return {
            "ok":                  True,
            "active_capabilities": identity.get("active_capabilities", []),
            "active_count":        identity.get("active_capability_count", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def self_awareness_run(request: "Request") -> "JSONResponse":
    """POST /api/self_awareness/run — trigger self-awareness synthesis."""
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
        from runtime.self_awareness import run_self_awareness
        result = run_self_awareness()
        return JSONResponse(status_code=200, content={
            "ok":                  True,
            "triggered_by":        operator_id,
            "readiness":           result["readiness"],
            "operating_mode":      result["operating_mode"],
            "active_capabilities": result["active_capabilities"],
            "critical_gaps":       result["critical_gaps"],
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"self-awareness run failed: {exc}"})


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_self_awareness_routes(app: Any) -> None:
    """Register AG-47 routes on a FastAPI app instance."""
    app.add_api_route("/api/self_awareness/latest",        self_awareness_latest,        methods=["GET"])
    app.add_api_route("/api/self_awareness/readiness",     self_awareness_readiness,     methods=["GET"])
    app.add_api_route("/api/self_awareness/posture",       self_awareness_posture,       methods=["GET"])
    app.add_api_route("/api/self_awareness/capabilities",  self_awareness_capabilities,  methods=["GET"])
    app.add_api_route("/api/self_awareness/run",           self_awareness_run,           methods=["POST"])
