"""AG-44: Supervisory Decision Queue Governance API handlers.

Read endpoints (no operator_id required):
  GET  /api/decision_queue/latest        — latest queue governance report
  GET  /api/decision_queue/summary       — slim summary
  GET  /api/decision_queue/state         — persisted queue state entries
  GET  /api/decision_queue/{decision_id} — single queue entry

Write endpoints (operator_id required, 403 without):
  POST /api/decision_queue/run           — trigger queue governance run
  POST /api/decision_queue/defer         — defer a decision
  POST /api/decision_queue/reopen        — reopen a deferred decision
  POST /api/decision_queue/supersede     — supersede a decision
  POST /api/decision_queue/archive       — archive a decision (terminal)

AG-44 invariant: queue governance only. No governance mutation, no campaign
mutation, no repair execution, no auto-approval. operator_action_required always.
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

async def decision_queue_latest() -> dict[str, Any]:
    """GET /api/decision_queue/latest — latest queue governance report."""
    try:
        data = _load_json("decision_queue_governance_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_queue_summary() -> dict[str, Any]:
    """GET /api/decision_queue/summary — slim summary."""
    try:
        data = _load_json("decision_queue_summary.json")
        if data is None:
            return {
                "ok": True, "open_count": 0, "deferred_count": 0,
                "stale_count": 0, "urgent_count": 0, "operating_mode": None,
            }
        return {
            "ok":             True,
            "open_count":     data.get("open_count", 0),
            "deferred_count": data.get("deferred_count", 0),
            "stale_count":    data.get("stale_count", 0),
            "urgent_count":   data.get("urgent_count", 0),
            "operating_mode": data.get("operating_mode"),
            "type_distribution": data.get("type_distribution", {}),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_queue_state() -> dict[str, Any]:
    """GET /api/decision_queue/state — persisted status entries."""
    try:
        data = _load_json("decision_queue_state.json")
        if data is None:
            return {"ok": True, "entries": {}}
        return {"ok": True, "entries": data.get("entries", {})}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_queue_by_id(decision_id: str) -> dict[str, Any]:
    """GET /api/decision_queue/{decision_id} — single queue entry."""
    try:
        data = _load_json("decision_queue_governance_latest.json")
        if data is None:
            return {"ok": False, "error": "no queue governance report found"}
        for entry in data.get("queue", []):
            if entry.get("decision_id") == decision_id:
                return {"ok": True, "decision_id": decision_id, "entry": entry}
        return {"ok": False, "error": f"decision_id {decision_id!r} not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------

def _extract_operator_id(body: dict, request: "Request") -> str:
    op = str(body.get("operator_id") or "").strip()
    if not op:
        op = str(request.headers.get("X-Operator-Id") or "").strip()
    return op


async def decision_queue_run(request: "Request") -> "JSONResponse":
    """POST /api/decision_queue/run — trigger queue governance run."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _extract_operator_id(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    try:
        from core.audit.decision_queue_governance import run_decision_queue_governance
        result = run_decision_queue_governance()
        return JSONResponse(status_code=200, content={
            "ok":             True,
            "triggered_by":   operator_id,
            "open_count":     result["open_count"],
            "deferred_count": result["deferred_count"],
            "stale_count":    result["stale_count"],
            "urgent_count":   result["urgent_count"],
            "operating_mode": result["operating_mode"],
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"queue governance failed: {exc}"})


async def decision_queue_defer(request: "Request") -> "JSONResponse":
    """POST /api/decision_queue/defer — defer a decision.

    Body: { "operator_id": "...", "decision_id": "...", "reason": "..." }
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _extract_operator_id(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    decision_id = str(body.get("decision_id") or "").strip()
    if not decision_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "decision_id required"})

    try:
        from core.audit.decision_queue_governance import defer_decision
        result = defer_decision(decision_id, operator_id, reason=str(body.get("reason") or ""))
        return JSONResponse(status_code=200 if result["ok"] else 409, content=result)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})


async def decision_queue_reopen(request: "Request") -> "JSONResponse":
    """POST /api/decision_queue/reopen — reopen a deferred decision."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _extract_operator_id(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    decision_id = str(body.get("decision_id") or "").strip()
    if not decision_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "decision_id required"})

    try:
        from core.audit.decision_queue_governance import reopen_decision
        result = reopen_decision(decision_id, operator_id, reason=str(body.get("reason") or ""))
        return JSONResponse(status_code=200 if result["ok"] else 409, content=result)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})


async def decision_queue_supersede(request: "Request") -> "JSONResponse":
    """POST /api/decision_queue/supersede — supersede a decision."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _extract_operator_id(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    decision_id   = str(body.get("decision_id") or "").strip()
    superseded_by = str(body.get("superseded_by") or "").strip()
    if not decision_id or not superseded_by:
        return JSONResponse(status_code=400, content={
            "ok": False, "reason": "decision_id and superseded_by required",
        })

    try:
        from core.audit.decision_queue_governance import supersede_decision
        result = supersede_decision(decision_id, operator_id, superseded_by=superseded_by)
        return JSONResponse(status_code=200 if result["ok"] else 409, content=result)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})


async def decision_queue_archive(request: "Request") -> "JSONResponse":
    """POST /api/decision_queue/archive — archive (terminal) a decision."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _extract_operator_id(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    decision_id = str(body.get("decision_id") or "").strip()
    if not decision_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "decision_id required"})

    try:
        from core.audit.decision_queue_governance import archive_decision
        result = archive_decision(decision_id, operator_id, reason=str(body.get("reason") or ""))
        return JSONResponse(status_code=200 if result["ok"] else 409, content=result)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_decision_queue_routes(app: Any) -> None:
    """Register AG-44 routes on a FastAPI app instance."""
    app.add_api_route("/api/decision_queue/latest",           decision_queue_latest,    methods=["GET"])
    app.add_api_route("/api/decision_queue/summary",          decision_queue_summary,   methods=["GET"])
    app.add_api_route("/api/decision_queue/state",            decision_queue_state,     methods=["GET"])
    app.add_api_route("/api/decision_queue/{decision_id}",    decision_queue_by_id,     methods=["GET"])
    app.add_api_route("/api/decision_queue/run",              decision_queue_run,       methods=["POST"])
    app.add_api_route("/api/decision_queue/defer",            decision_queue_defer,     methods=["POST"])
    app.add_api_route("/api/decision_queue/reopen",           decision_queue_reopen,    methods=["POST"])
    app.add_api_route("/api/decision_queue/supersede",        decision_queue_supersede, methods=["POST"])
    app.add_api_route("/api/decision_queue/archive",          decision_queue_archive,   methods=["POST"])
