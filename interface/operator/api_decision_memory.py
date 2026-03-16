"""AG-45: Operator Decision Session Memory API handlers.

Read endpoints (no operator_id required):
  GET  /api/decision_memory/latest         — latest memory report
  GET  /api/decision_memory/index          — memory entry index
  GET  /api/decision_memory/context        — enriched open decisions with context
  GET  /api/decision_memory/{memory_id}    — single memory entry by ID

Write endpoint (operator_id required, 403 without):
  POST /api/decision_memory/run            — trigger memory generation

AG-45 invariant: context-memory only. No governance mutation, no queue
mutation, no campaign mutation, no repair execution, no baseline mutation,
no auto-decision outcome changes.
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

async def decision_memory_latest() -> dict[str, Any]:
    """GET /api/decision_memory/latest — latest memory report."""
    try:
        data = _load_json("operator_decision_memory_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_memory_index() -> dict[str, Any]:
    """GET /api/decision_memory/index — memory entry index."""
    try:
        data = _load_json("operator_decision_memory_index.json")
        if data is None:
            return {"ok": True, "memory_entries": 0, "index": []}
        return {
            "ok":             True,
            "memory_entries": data.get("memory_entries", 0),
            "top_pattern":    data.get("top_pattern"),
            "index":          data.get("index", []),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_memory_context() -> dict[str, Any]:
    """GET /api/decision_memory/context — enriched open decisions with memory context."""
    try:
        data = _load_json("operator_decision_memory_latest.json")
        if data is None:
            return {"ok": True, "enriched_packages": [], "memory_entries": 0}
        return {
            "ok":               True,
            "enriched_packages": data.get("enriched_packages", []),
            "memory_entries":   data.get("memory_entries", 0),
            "top_pattern":      data.get("top_pattern"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def decision_memory_by_id(memory_id: str) -> dict[str, Any]:
    """GET /api/decision_memory/{memory_id} — single memory entry."""
    try:
        data = _load_json("operator_decision_memory_latest.json")
        if data is None:
            return {"ok": False, "error": "no memory report found"}
        for entry in data.get("memories", []):
            if entry.get("memory_id") == memory_id:
                return {"ok": True, "memory_id": memory_id, "entry": entry}
        return {"ok": False, "error": f"memory_id {memory_id!r} not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def decision_memory_run(request: "Request") -> "JSONResponse":
    """POST /api/decision_memory/run — trigger memory generation run."""
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
        from core.audit.operator_decision_memory import run_operator_decision_memory
        result = run_operator_decision_memory()
        return JSONResponse(status_code=200, content={
            "ok":             True,
            "triggered_by":   operator_id,
            "memory_entries": result["memory_entries"],
            "top_pattern":    result["top_pattern"],
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"memory run failed: {exc}"})


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_decision_memory_routes(app: Any) -> None:
    """Register AG-45 routes on a FastAPI app instance."""
    app.add_api_route("/api/decision_memory/latest",          decision_memory_latest,   methods=["GET"])
    app.add_api_route("/api/decision_memory/index",           decision_memory_index,    methods=["GET"])
    app.add_api_route("/api/decision_memory/context",         decision_memory_context,  methods=["GET"])
    app.add_api_route("/api/decision_memory/{memory_id}",     decision_memory_by_id,    methods=["GET"])
    app.add_api_route("/api/decision_memory/run",             decision_memory_run,      methods=["POST"])
