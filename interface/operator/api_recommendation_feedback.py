"""AG-54: Recommendation Feedback Loop API handlers.

Read endpoints (no operator_id required):
  GET  /api/recommendation_feedback/latest   — latest feedback report
  GET  /api/recommendation_feedback/index    — slim feedback index
  GET  /api/recommendation_feedback/classes  — feedback class list
  GET  /api/recommendation_feedback/gaps     — ignored/overridden entries only

Write endpoint (operator_id required, 403 without):
  POST /api/recommendation_feedback/run      — trigger feedback run

AG-54 invariant: feedback-only. No mutation, no enforcement,
no auto-approval, no repair execution.
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

from runtime.recommendation_feedback_policy import FEEDBACK_CLASSES


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


async def recommendation_feedback_latest() -> dict[str, Any]:
    """GET /api/recommendation_feedback/latest — latest feedback report."""
    try:
        data = _load_json("runtime_recommendation_feedback_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def recommendation_feedback_index() -> dict[str, Any]:
    """GET /api/recommendation_feedback/index — slim feedback index."""
    try:
        data = _load_json("runtime_recommendation_feedback_index.json")
        if data is None:
            return {
                "ok": True,
                "recommendations_total": 0,
                "feedback_counts": {cls: 0 for cls in FEEDBACK_CLASSES},
                "gap_count": 0,
            }
        return {
            "ok":                    True,
            "recommendations_total": data.get("recommendations_total", 0),
            "feedback_counts":       data.get("feedback_counts", {}),
            "gap_count":             data.get("gap_count", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def recommendation_feedback_classes() -> dict[str, Any]:
    """GET /api/recommendation_feedback/classes — feedback class list."""
    try:
        return {"ok": True, "feedback_classes": FEEDBACK_CLASSES}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def recommendation_feedback_gaps() -> dict[str, Any]:
    """GET /api/recommendation_feedback/gaps — ignored/overridden entries only."""
    try:
        data = _load_json("runtime_recommendation_feedback_latest.json")
        if data is None:
            return {"ok": True, "gaps": [], "gap_count": 0}
        gaps = data.get("gaps", [])
        return {"ok": True, "gaps": gaps, "gap_count": len(gaps)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def recommendation_feedback_run(request: "Request") -> "JSONResponse":
    """POST /api/recommendation_feedback/run — trigger feedback run."""
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
        from runtime.recommendation_feedback import run_recommendation_feedback
        result = run_recommendation_feedback()
        return JSONResponse(status_code=200, content={
            "ok":                    True,
            "triggered_by":          operator_id,
            "recommendations_total": result.get("recommendations_total", 0),
            "feedback_counts":       result.get("feedback_counts", {}),
            "gap_count":             result.get("gap_count", 0),
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"feedback run failed: {exc}"})


def register_recommendation_feedback_routes(app: Any) -> None:
    """Register AG-54 routes on a FastAPI app instance."""
    app.add_api_route("/api/recommendation_feedback/latest",  recommendation_feedback_latest,  methods=["GET"])
    app.add_api_route("/api/recommendation_feedback/index",   recommendation_feedback_index,   methods=["GET"])
    app.add_api_route("/api/recommendation_feedback/classes", recommendation_feedback_classes, methods=["GET"])
    app.add_api_route("/api/recommendation_feedback/gaps",    recommendation_feedback_gaps,    methods=["GET"])
    app.add_api_route("/api/recommendation_feedback/run",     recommendation_feedback_run,     methods=["POST"])
