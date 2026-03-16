"""AG-52: Runtime Recommendation Governance Gate API handlers.

Read endpoints (no operator_id required):
  GET  /api/governance_gate/latest   — latest gate report
  GET  /api/governance_gate/index    — slim index
  GET  /api/governance_gate/classes  — governance classes and review levels
  GET  /api/governance_gate/alerts   — only HIGH_SENSITIVITY and CRITICAL_GOVERNANCE items

Write endpoint (operator_id required, 403 without):
  POST /api/governance_gate/run      — trigger governance gate run

AG-52 invariant: advisory-only. Classification only. No governance mutation,
no campaign mutation, no repair execution, no automatic claim correction.
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


async def governance_gate_latest() -> dict[str, Any]:
    """GET /api/governance_gate/latest — latest gate report."""
    try:
        data = _load_json("runtime_governance_gate_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def governance_gate_index() -> dict[str, Any]:
    """GET /api/governance_gate/index — slim governance gate index."""
    try:
        data = _load_json("runtime_governance_gate_index.json")
        if data is None:
            return {
                "ok": True,
                "total_count": 0,
                "high_sensitivity": 0,
                "critical": 0,
                "governance_summary": {},
            }
        return {
            "ok":                True,
            "total_count":       data.get("total_count", 0),
            "high_sensitivity":  data.get("high_sensitivity", 0),
            "critical":          data.get("critical", 0),
            "governance_summary": data.get("governance_summary", {}),
            "ts":                data.get("ts"),
            "run_id":            data.get("run_id"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def governance_gate_classes() -> dict[str, Any]:
    """GET /api/governance_gate/classes — available governance classes and review levels."""
    try:
        from runtime.governance_gate_policy import (
            GOVERNANCE_CLASSES,
            REVIEW_LEVELS,
            GOVERNANCE_CLASS_TO_REVIEW_LEVEL,
        )
        return {
            "ok":                              True,
            "governance_classes":              GOVERNANCE_CLASSES,
            "review_levels":                   REVIEW_LEVELS,
            "governance_class_to_review_level": GOVERNANCE_CLASS_TO_REVIEW_LEVEL,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def governance_gate_alerts() -> dict[str, Any]:
    """GET /api/governance_gate/alerts — HIGH_SENSITIVITY and CRITICAL_GOVERNANCE items only."""
    try:
        data = _load_json("runtime_governance_gate_latest.json")
        if data is None:
            return {"ok": True, "alerts": [], "alert_count": 0}
        gated = data.get("gated_recommendations", [])
        alerts = [
            g for g in gated
            if g.get("governance_class") in ("HIGH_SENSITIVITY", "CRITICAL_GOVERNANCE")
        ]
        return {
            "ok":          True,
            "alerts":      alerts,
            "alert_count": len(alerts),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def governance_gate_run(request: "Request") -> "JSONResponse":
    """POST /api/governance_gate/run — trigger governance gate run."""
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
        from runtime.recommendation_governance_gate import run_recommendation_governance_gate
        result = run_recommendation_governance_gate()
        return JSONResponse(status_code=200, content={
            "ok":              True,
            "triggered_by":    operator_id,
            "total_count":     result.get("total_count"),
            "high_sensitivity": result.get("high_sensitivity"),
            "critical":        result.get("critical"),
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"gate run failed: {exc}"})


def register_governance_gate_routes(app: Any) -> None:
    """Register AG-52 routes on a FastAPI app instance."""
    app.add_api_route("/api/governance_gate/latest",  governance_gate_latest,  methods=["GET"])
    app.add_api_route("/api/governance_gate/index",   governance_gate_index,   methods=["GET"])
    app.add_api_route("/api/governance_gate/classes", governance_gate_classes, methods=["GET"])
    app.add_api_route("/api/governance_gate/alerts",  governance_gate_alerts,  methods=["GET"])
    app.add_api_route("/api/governance_gate/run",     governance_gate_run,     methods=["POST"])
