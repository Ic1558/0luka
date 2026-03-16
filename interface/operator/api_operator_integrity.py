"""AG-53: Operator Decision Flow Integrity API handlers.

Read endpoints (no operator_id required):
  GET  /api/operator_integrity/latest   — latest integrity report
  GET  /api/operator_integrity/index    — slim integrity index
  GET  /api/operator_integrity/broken   — broken lifecycle chains only

Write endpoint (operator_id required, 403 without):
  POST /api/operator_integrity/run      — trigger integrity validation run

AG-53 invariant: validation-only. No mutation, no enforcement,
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


async def operator_integrity_latest() -> dict[str, Any]:
    """GET /api/operator_integrity/latest — latest integrity report."""
    try:
        data = _load_json("runtime_operator_decision_integrity_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def operator_integrity_index() -> dict[str, Any]:
    """GET /api/operator_integrity/index — slim integrity index."""
    try:
        data = _load_json("runtime_operator_decision_integrity_index.json")
        if data is None:
            return {
                "ok": True,
                "recommendations_checked": 0, "valid_lifecycle": 0,
                "broken_chain": 0, "missing_queue": 0, "missing_memory": 0,
            }
        return {
            "ok":                      True,
            "recommendations_checked": data.get("recommendations_checked", 0),
            "valid_lifecycle":         data.get("valid_lifecycle", 0),
            "broken_chain":            data.get("broken_chain", 0),
            "missing_queue":           data.get("missing_queue", 0),
            "missing_memory":          data.get("missing_memory", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def operator_integrity_broken() -> dict[str, Any]:
    """GET /api/operator_integrity/broken — broken lifecycle chains only."""
    try:
        data = _load_json("runtime_operator_decision_integrity_latest.json")
        if data is None:
            return {"ok": True, "broken_results": [], "broken_chain": 0}
        broken = data.get("broken_results", [])
        return {
            "ok":             True,
            "broken_results": broken,
            "broken_chain":   len(broken),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def operator_integrity_run(request: "Request") -> "JSONResponse":
    """POST /api/operator_integrity/run — trigger integrity validation run."""
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
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        result = run_operator_decision_integrity()
        return JSONResponse(status_code=200, content={
            "ok":                      True,
            "triggered_by":            operator_id,
            "recommendations_checked": result["recommendations_checked"],
            "valid_lifecycle":         result["valid_lifecycle"],
            "broken_chain":            result["broken_chain"],
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"integrity run failed: {exc}"})


def register_operator_integrity_routes(app: Any) -> None:
    """Register AG-53 routes on a FastAPI app instance."""
    app.add_api_route("/api/operator_integrity/latest", operator_integrity_latest, methods=["GET"])
    app.add_api_route("/api/operator_integrity/index",  operator_integrity_index,  methods=["GET"])
    app.add_api_route("/api/operator_integrity/broken", operator_integrity_broken, methods=["GET"])
    app.add_api_route("/api/operator_integrity/run",    operator_integrity_run,    methods=["POST"])
