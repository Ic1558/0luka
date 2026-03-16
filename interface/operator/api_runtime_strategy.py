"""AG-42: Supervisory Runtime Strategy API handlers.

Read endpoints (no operator_id required):
  GET  /api/runtime_strategy/latest          — latest strategy report
  GET  /api/runtime_strategy/mode            — current operating mode snapshot
  GET  /api/runtime_strategy/recommendations — current advisory recommendations
  GET  /api/runtime_strategy/risks           — current key risks

Write endpoint (operator_id required, 403 without):
  POST /api/runtime_strategy/run             — trigger strategy analysis

AG-42 invariant: advisory-only. No governance mutation, no campaign mutation,
                 no repair execution, no auto-mode switch. operator_action_required always.
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

async def runtime_strategy_latest() -> dict[str, Any]:
    """GET /api/runtime_strategy/latest — latest strategy report."""
    try:
        data = _load_json("runtime_strategy_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def runtime_strategy_mode() -> dict[str, Any]:
    """GET /api/runtime_strategy/mode — current operating mode snapshot."""
    try:
        data = _load_json("runtime_operating_mode.json")
        if data is None:
            return {"ok": True, "operating_mode": None, "confidence": None}
        return {
            "ok":             True,
            "operating_mode": data.get("operating_mode"),
            "confidence":     data.get("confidence"),
            "reasons":        data.get("reasons", []),
            "key_risks":      data.get("key_risks", []),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def runtime_strategy_recommendations() -> dict[str, Any]:
    """GET /api/runtime_strategy/recommendations — current advisory recommendations."""
    try:
        data = _load_json("runtime_strategy_latest.json")
        if data is None:
            return {"ok": True, "recommendations": [], "total": 0}
        recs = data.get("recommendations", [])
        return {
            "ok":             True,
            "recommendations": recs,
            "total":          len(recs),
            "operating_mode": data.get("operating_mode"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def runtime_strategy_risks() -> dict[str, Any]:
    """GET /api/runtime_strategy/risks — current key risks."""
    try:
        data = _load_json("runtime_operating_mode.json")
        if data is None:
            return {"ok": True, "key_risks": [], "operating_mode": None}
        return {
            "ok":             True,
            "key_risks":      data.get("key_risks", []),
            "operating_mode": data.get("operating_mode"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def runtime_strategy_run(request: "Request") -> "JSONResponse":
    """POST /api/runtime_strategy/run — trigger supervisory runtime strategy analysis.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Advisory-only. No governance mutation. No campaign mutation. No repair execution.
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
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        result = run_runtime_strategy()
        return JSONResponse(
            status_code=200,
            content={
                "ok":                   True,
                "triggered_by":         operator_id,
                "operating_mode":       result["operating_mode"],
                "mode_confidence":      result["mode_confidence"],
                "recommendations":      result["recommendation_count"],
                "top_risk":             result["key_risks"][0] if result["key_risks"] else None,
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"strategy analysis failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_runtime_strategy_routes(app: Any) -> None:
    """Register AG-42 routes on a FastAPI app instance."""
    app.add_api_route("/api/runtime_strategy/latest",          runtime_strategy_latest,          methods=["GET"])
    app.add_api_route("/api/runtime_strategy/mode",            runtime_strategy_mode,             methods=["GET"])
    app.add_api_route("/api/runtime_strategy/recommendations", runtime_strategy_recommendations,  methods=["GET"])
    app.add_api_route("/api/runtime_strategy/risks",           runtime_strategy_risks,            methods=["GET"])
    app.add_api_route("/api/runtime_strategy/run",             runtime_strategy_run,              methods=["POST"])
