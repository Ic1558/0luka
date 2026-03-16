"""AG-37: Drift Intelligence Layer API handlers.

Read endpoints (no operator_id required):
  GET  /api/drift_intelligence/latest     — latest intelligence report
  GET  /api/drift_intelligence/patterns   — detected drift patterns
  GET  /api/drift_intelligence/hotspots   — drift hotspot components
  GET  /api/drift_intelligence/stability  — runtime stability score

Write endpoint (operator_id required, 403 without):
  POST /api/drift_intelligence/run        — trigger intelligence analysis run

AG-37 invariant: intelligence-only. No governance mutation, no baseline mutation,
                 no repair execution, no finding lifecycle changes.
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


def _load_latest(runtime_root: str | None = None) -> dict[str, Any]:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        return {}
    path = Path(rt) / "state" / "drift_intelligence_latest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

async def drift_intelligence_latest() -> dict[str, Any]:
    """GET /api/drift_intelligence/latest — latest intelligence report."""
    try:
        report = _load_latest()
        return {"ok": True, "report": report}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_intelligence_patterns() -> dict[str, Any]:
    """GET /api/drift_intelligence/patterns — detected recurring drift patterns."""
    try:
        rt = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
        if not rt:
            return {"ok": True, "patterns": [], "total": 0}
        path = Path(rt) / "state" / "drift_pattern_registry.json"
        if not path.exists():
            return {"ok": True, "patterns": [], "total": 0}
        registry = json.loads(path.read_text(encoding="utf-8"))
        patterns = registry.get("patterns", [])
        return {"ok": True, "patterns": patterns, "total": len(patterns)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_intelligence_hotspots() -> dict[str, Any]:
    """GET /api/drift_intelligence/hotspots — drift hotspot components."""
    try:
        report = _load_latest()
        hotspots = report.get("hotspot_components", [])
        return {"ok": True, "hotspots": hotspots, "total": len(hotspots)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_intelligence_stability() -> dict[str, Any]:
    """GET /api/drift_intelligence/stability — runtime stability score."""
    try:
        rt = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
        if not rt:
            return {"ok": True, "stability": {}}
        path = Path(rt) / "state" / "runtime_stability_score.json"
        if not path.exists():
            return {"ok": True, "stability": {}}
        stability = json.loads(path.read_text(encoding="utf-8"))
        return {"ok": True, "stability": stability}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def drift_intelligence_run(request: "Request") -> "JSONResponse":
    """POST /api/drift_intelligence/run — trigger drift intelligence analysis.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Analysis-only. No governance mutation. No repair execution.
    """
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
        from core.audit.drift_intelligence import run_drift_intelligence
        result = run_drift_intelligence()
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "triggered_by": operator_id,
                "patterns_detected": result["patterns_detected"],
                "stability_score": result["stability_score"],
                "classification": result["classification"],
                "hotspots": result["hotspots"],
                "recommendations": result["recommendations"],
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"intelligence run failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_drift_intelligence_routes(app: Any) -> None:
    """Register AG-37 routes on a FastAPI app instance."""
    app.add_api_route("/api/drift_intelligence/latest",    drift_intelligence_latest,    methods=["GET"])
    app.add_api_route("/api/drift_intelligence/patterns",  drift_intelligence_patterns,  methods=["GET"])
    app.add_api_route("/api/drift_intelligence/hotspots",  drift_intelligence_hotspots,  methods=["GET"])
    app.add_api_route("/api/drift_intelligence/stability", drift_intelligence_stability, methods=["GET"])
    app.add_api_route("/api/drift_intelligence/run",       drift_intelligence_run,       methods=["POST"])
