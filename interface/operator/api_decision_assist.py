"""AG-43: Operator Decision Assist API handlers.

Read endpoints (no operator_id required):
  GET  /api/decision_assist/latest              — latest decision assist report
  GET  /api/decision_assist/queue               — current decision queue
  GET  /api/decision_assist/{decision_id}       — one decision package by ID
  GET  /api/decision_assist/summary             — high-level summary

Write endpoint (operator_id required, 403 without):
  POST /api/decision_assist/run                 — trigger decision assist run

AG-43 invariant: assist-only. No governance mutation, no campaign mutation,
                 no repair execution, no auto-approval. operator_action_required always.
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

async def decision_assist_latest() -> dict[str, Any]:
    """GET /api/decision_assist/latest — latest decision assist report."""
    try:
        data = _load_json("operator_decision_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_assist_queue() -> dict[str, Any]:
    """GET /api/decision_assist/queue — current decision queue."""
    try:
        data = _load_json("operator_decision_queue.json")
        if data is None:
            return {"ok": True, "packages": [], "pending": 0, "operating_mode": None}
        return {
            "ok":             True,
            "packages":       data.get("packages", []),
            "pending":        data.get("pending", 0),
            "urgent_count":   data.get("urgent_count", 0),
            "operating_mode": data.get("operating_mode"),
            "type_distribution": data.get("type_distribution", {}),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_assist_by_id(decision_id: str) -> dict[str, Any]:
    """GET /api/decision_assist/{decision_id} — one decision package by ID."""
    try:
        data = _load_json("operator_decision_queue.json")
        if data is None:
            return {"ok": False, "error": "no decision queue found"}
        for pkg in data.get("packages", []):
            if pkg.get("decision_id") == decision_id:
                return {"ok": True, "decision_id": decision_id, "package": pkg}
        return {"ok": False, "error": f"decision_id {decision_id!r} not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_assist_summary() -> dict[str, Any]:
    """GET /api/decision_assist/summary — high-level summary."""
    try:
        data = _load_json("operator_decision_latest.json")
        if data is None:
            return {
                "ok": True, "pending_decisions": 0, "urgent_count": 0,
                "top_decision_type": None, "operating_mode": None,
            }
        top = data.get("top_decision")
        return {
            "ok":                True,
            "pending_decisions": data.get("pending_decisions", 0),
            "urgent_count":      data.get("urgent_count", 0),
            "deferred_count":    data.get("deferred_count", 0),
            "top_decision_type": top["decision_type"] if top else None,
            "operating_mode":    data.get("operating_mode"),
            "key_risks":         data.get("key_risks", []),
            "type_distribution": data.get("type_distribution", {}),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def decision_assist_run(request: "Request") -> "JSONResponse":
    """POST /api/decision_assist/run — trigger operator decision assist analysis.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Assist-only. No governance mutation. No campaign mutation. No repair execution.
    No auto-approval.
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
        from core.audit.operator_decision_assist import run_operator_decision_assist
        result = run_operator_decision_assist()
        return JSONResponse(
            status_code=200,
            content={
                "ok":                True,
                "triggered_by":      operator_id,
                "pending_decisions": result["pending_decisions"],
                "urgent_count":      result["urgent_count"],
                "top_decision_type": result["top_decision_type"],
                "operating_mode":    result["operating_mode"],
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"decision assist failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_decision_assist_routes(app: Any) -> None:
    """Register AG-43 routes on a FastAPI app instance."""
    app.add_api_route("/api/decision_assist/latest",           decision_assist_latest,    methods=["GET"])
    app.add_api_route("/api/decision_assist/queue",            decision_assist_queue,     methods=["GET"])
    app.add_api_route("/api/decision_assist/summary",          decision_assist_summary,   methods=["GET"])
    app.add_api_route("/api/decision_assist/{decision_id}",    decision_assist_by_id,     methods=["GET"])
    app.add_api_route("/api/decision_assist/run",              decision_assist_run,       methods=["POST"])
