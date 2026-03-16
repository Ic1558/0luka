"""AG-41: Repair Campaign Outcome Intelligence API handlers.

Read endpoints (no operator_id required):
  GET  /api/campaign_outcome/latest      — latest outcome intelligence report
  GET  /api/campaign_outcome/scores      — campaign effectiveness scores
  GET  /api/campaign_outcome/patterns    — detected campaign patterns
  GET  /api/campaign_outcome/regressions — detected campaign regressions

Write endpoint (operator_id required, 403 without):
  POST /api/campaign_outcome/run         — trigger outcome intelligence run

AG-41 invariant: intelligence-only. No campaign mutation, no governance mutation,
                 no repair execution, no baseline mutation. operator_action_required always.
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

async def campaign_outcome_latest() -> dict[str, Any]:
    """GET /api/campaign_outcome/latest — latest outcome intelligence report."""
    try:
        data = _load_json("repair_campaign_outcome_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def campaign_outcome_scores() -> dict[str, Any]:
    """GET /api/campaign_outcome/scores — campaign effectiveness scores."""
    try:
        data = _load_json("campaign_effectiveness_score.json")
        if data is None:
            return {"ok": True, "scored_campaigns": [], "aggregate_effectiveness": {}}
        return {
            "ok": True,
            "scored_campaigns": data.get("scored_campaigns", []),
            "aggregate_effectiveness": data.get("aggregate_effectiveness", {}),
            "outcome_distribution": data.get("outcome_distribution", {}),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def campaign_outcome_patterns() -> dict[str, Any]:
    """GET /api/campaign_outcome/patterns — detected campaign patterns."""
    try:
        data = _load_json("campaign_pattern_registry.json")
        if data is None:
            return {"ok": True, "patterns": [], "overall_recommendation": None}
        return {
            "ok": True,
            "patterns": data.get("patterns", []),
            "overall_recommendation": data.get("overall_recommendation"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def campaign_outcome_regressions() -> dict[str, Any]:
    """GET /api/campaign_outcome/regressions — detected campaign regressions."""
    try:
        data = _load_json("repair_campaign_outcome_latest.json")
        if data is None:
            return {"ok": True, "regressions": []}
        return {
            "ok": True,
            "regressions": data.get("regressions", []),
            "total": len(data.get("regressions", [])),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def campaign_outcome_run(request: "Request") -> "JSONResponse":
    """POST /api/campaign_outcome/run — trigger campaign outcome intelligence.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Intelligence-only. No campaign mutation. No governance mutation. No repair execution.
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
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        result = run_campaign_outcome_intelligence()
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "triggered_by":      operator_id,
                "campaign_count":    result["campaign_count"],
                "patterns_detected": result["patterns_detected"],
                "regressions_found": result["regressions_found"],
                "overall_recommendation": result["overall_recommendation"],
                "aggregate_effectiveness": result["aggregate_effectiveness"],
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"campaign outcome intelligence failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_campaign_outcome_routes(app: Any) -> None:
    """Register AG-41 routes on a FastAPI app instance."""
    app.add_api_route("/api/campaign_outcome/latest",      campaign_outcome_latest,      methods=["GET"])
    app.add_api_route("/api/campaign_outcome/scores",      campaign_outcome_scores,      methods=["GET"])
    app.add_api_route("/api/campaign_outcome/patterns",    campaign_outcome_patterns,    methods=["GET"])
    app.add_api_route("/api/campaign_outcome/regressions", campaign_outcome_regressions, methods=["GET"])
    app.add_api_route("/api/campaign_outcome/run",         campaign_outcome_run,         methods=["POST"])
