"""AG-57: System Self-Audit Layer API handlers.

Read endpoints (no operator_id required):
  GET  /api/system_self_audit/latest   — latest audit report
  GET  /api/system_self_audit/index    — slim audit index
  GET  /api/system_self_audit/verdicts — audit verdict class list
  GET  /api/system_self_audit/gaps     — missing/incoherent findings

Write endpoint (operator_id required, 403 without):
  POST /api/system_self_audit/run      — trigger audit run

AG-57 invariant: audit-only. No mutation, no auto-correction,
no repair execution, no governance outcome enforcement.
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

from runtime.system_self_audit_policy import AUDIT_VERDICTS


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


async def system_self_audit_latest() -> dict[str, Any]:
    """GET /api/system_self_audit/latest — latest audit report."""
    try:
        data = _load_json("runtime_system_self_audit_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def system_self_audit_index() -> dict[str, Any]:
    """GET /api/system_self_audit/index — slim audit index."""
    try:
        data = _load_json("runtime_system_self_audit_index.json")
        if data is None:
            return {
                "ok": True, "verdict": "STACK_UNTRUSTED",
                "missing_count": 0, "incoherent_count": 0, "gaps": [],
            }
        return {
            "ok":              True,
            "verdict":         data.get("verdict", "STACK_UNTRUSTED"),
            "missing_count":   data.get("missing_count", 0),
            "incoherent_count": data.get("incoherent_count", 0),
            "gaps":            data.get("gaps", []),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def system_self_audit_verdicts() -> dict[str, Any]:
    """GET /api/system_self_audit/verdicts — audit verdict class list."""
    try:
        return {"ok": True, "verdicts": AUDIT_VERDICTS}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def system_self_audit_gaps() -> dict[str, Any]:
    """GET /api/system_self_audit/gaps — missing/incoherent findings."""
    try:
        data = _load_json("runtime_system_self_audit_latest.json")
        if data is None:
            return {"ok": True, "gaps": [], "missing_count": 0, "incoherent_count": 0}
        coherence = data.get("coherence", {})
        return {
            "ok":              True,
            "gaps":            data.get("gaps", []),
            "missing":         coherence.get("missing", []),
            "incoherent":      coherence.get("incoherent", []),
            "missing_count":   data.get("missing_count", 0),
            "incoherent_count": data.get("incoherent_count", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def system_self_audit_run(request: "Request") -> "JSONResponse":
    """POST /api/system_self_audit/run — trigger audit run."""
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
        from runtime.system_self_audit import run_system_self_audit
        result = run_system_self_audit()
        return JSONResponse(status_code=200, content={
            "ok":            True,
            "triggered_by":  operator_id,
            "verdict":       result.get("verdict"),
            "missing_count": result.get("missing_count", 0),
            "gaps":          result.get("gaps", []),
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"audit run failed: {exc}"})


def register_system_self_audit_routes(app: Any) -> None:
    """Register AG-57 routes on a FastAPI app instance."""
    app.add_api_route("/api/system_self_audit/latest",   system_self_audit_latest,   methods=["GET"])
    app.add_api_route("/api/system_self_audit/index",    system_self_audit_index,    methods=["GET"])
    app.add_api_route("/api/system_self_audit/verdicts", system_self_audit_verdicts, methods=["GET"])
    app.add_api_route("/api/system_self_audit/gaps",     system_self_audit_gaps,     methods=["GET"])
    app.add_api_route("/api/system_self_audit/run",      system_self_audit_run,      methods=["POST"])
