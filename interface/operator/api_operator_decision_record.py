from pathlib import Path
"""AG-60: Operator Decision Record API."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False


def _state_dir():
    return Path(os.environ.get("LUKA_RUNTIME_ROOT", str(Path.home() / "0luka_runtime"))) / "state"

def _load(f):
    p = _state_dir() / f
    return json.loads(p.read_text()) if p.exists() else None


async def decision_record_create(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid JSON"}, status_code=400)
    try:
        from runtime.operator_decision_record import record_decision
        rec = record_decision(
            operator_id=body.get("operator_id", "unknown"),
            action=body.get("action", ""),
            reason=body.get("reason", ""),
            trace_id=body.get("trace_id"),
            governance_id=body.get("governance_id"),
            recommendation_id=body.get("recommendation_id"),
            evidence_refs=body.get("evidence_refs", []),
        )
        return JSONResponse({"ok": True, "decision_record_id": rec["decision_record_id"]})
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

async def decision_record_latest(request: Request) -> JSONResponse:
    d = _load("runtime_operator_decision_record_latest.json")
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)

async def decision_record_index(request: Request) -> JSONResponse:
    return JSONResponse({"decisions": _load("runtime_operator_decision_record_index.json") or []})


def register_operator_decision_record_routes(app: Any) -> None:
    app.add_api_route("/api/operator_decision_record", decision_record_create, methods=["POST"])
    app.add_api_route("/api/operator_decision_record/latest", decision_record_latest, methods=["GET"])
    app.add_api_route("/api/operator_decision_record/index", decision_record_index, methods=["GET"])
