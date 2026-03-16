"""AG-51: Operator Confidence Calibration API handlers.

Read endpoints (no operator_id required):
  GET  /api/operator_confidence/latest        — latest calibration report
  GET  /api/operator_confidence/index         — slim index
  GET  /api/operator_confidence/calibrations  — per-dimension calibrations
  GET  /api/operator_confidence/classes       — available confidence classes

Write endpoint (operator_id required, 403 without):
  POST /api/operator_confidence/run           — trigger calibration run

AG-51 invariant: advisory-only. No governance mutation, no campaign
mutation, no repair execution, no automatic claim correction.
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


async def operator_confidence_latest() -> dict[str, Any]:
    """GET /api/operator_confidence/latest — latest calibration report."""
    try:
        data = _load_json("runtime_operator_confidence_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def operator_confidence_index() -> dict[str, Any]:
    """GET /api/operator_confidence/index — slim confidence index."""
    try:
        data = _load_json("runtime_operator_confidence_index.json")
        if data is None:
            return {
                "ok": True,
                "overall_confidence_score": None,
                "overall_confidence_class": None,
                "dimension_count": 0,
            }
        return {
            "ok":                     True,
            "overall_confidence_score": data.get("overall_confidence_score"),
            "overall_confidence_class": data.get("overall_confidence_class"),
            "dimension_count":        data.get("dimension_count", 0),
            "ts":                     data.get("ts"),
            "run_id":                 data.get("run_id"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def operator_confidence_calibrations() -> dict[str, Any]:
    """GET /api/operator_confidence/calibrations — per-dimension calibrations."""
    try:
        data = _load_json("runtime_operator_confidence_latest.json")
        if data is None:
            return {"ok": True, "calibrations": [], "dimension_count": 0}
        calibrations = data.get("calibrations", [])
        return {
            "ok":              True,
            "calibrations":    calibrations,
            "dimension_count": len(calibrations),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def operator_confidence_classes() -> dict[str, Any]:
    """GET /api/operator_confidence/classes — available confidence classes."""
    try:
        from runtime.operator_confidence_policy import CONFIDENCE_CLASSES, CALIBRATION_DIMENSIONS, WEIGHT_BY_DIMENSION
        return {
            "ok":                   True,
            "confidence_classes":   CONFIDENCE_CLASSES,
            "calibration_dimensions": CALIBRATION_DIMENSIONS,
            "weight_by_dimension":  WEIGHT_BY_DIMENSION,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def operator_confidence_run(request: "Request") -> "JSONResponse":
    """POST /api/operator_confidence/run — trigger calibration run."""
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
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        result = run_operator_confidence_calibration()
        return JSONResponse(status_code=200, content={
            "ok":                     True,
            "triggered_by":           operator_id,
            "overall_confidence_score": result.get("overall_confidence_score"),
            "overall_confidence_class": result.get("overall_confidence_class"),
            "dimension_count":        result.get("dimension_count"),
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"calibration run failed: {exc}"})


def register_operator_confidence_routes(app: Any) -> None:
    """Register AG-51 routes on a FastAPI app instance."""
    app.add_api_route("/api/operator_confidence/latest",       operator_confidence_latest,       methods=["GET"])
    app.add_api_route("/api/operator_confidence/index",        operator_confidence_index,        methods=["GET"])
    app.add_api_route("/api/operator_confidence/calibrations", operator_confidence_calibrations, methods=["GET"])
    app.add_api_route("/api/operator_confidence/classes",      operator_confidence_classes,      methods=["GET"])
    app.add_api_route("/api/operator_confidence/run",          operator_confidence_run,          methods=["POST"])
