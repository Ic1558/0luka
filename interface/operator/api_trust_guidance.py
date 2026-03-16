"""AG-50: Runtime Trust-Aware Operator Guidance API handlers.

Read endpoints (no operator_id required):
  GET  /api/trust_guidance/latest   — latest guidance report
  GET  /api/trust_guidance/index    — slim guidance index
  GET  /api/trust_guidance/entries  — guidance entries
  GET  /api/trust_guidance/mode     — current guidance mode

Write endpoint (operator_id required, 403 without):
  POST /api/trust_guidance/run      — trigger guidance run

AG-50 invariant: advisory-only. No governance mutation, no campaign
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


async def trust_guidance_latest() -> dict[str, Any]:
    """GET /api/trust_guidance/latest — latest guidance report."""
    try:
        data = _load_json("runtime_trust_guidance_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def trust_guidance_index() -> dict[str, Any]:
    """GET /api/trust_guidance/index — slim guidance index."""
    try:
        data = _load_json("runtime_trust_guidance_index.json")
        if data is None:
            return {
                "ok": True, "guidance_mode": None,
                "caution_class": None, "overall_trust_score": None,
                "overall_trust_class": None, "entry_count": 0,
            }
        return {
            "ok":                  True,
            "guidance_mode":       data.get("guidance_mode"),
            "caution_class":       data.get("caution_class"),
            "overall_trust_score": data.get("overall_trust_score"),
            "overall_trust_class": data.get("overall_trust_class"),
            "gap_count":           data.get("gap_count", 0),
            "entry_count":         data.get("entry_count", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def trust_guidance_entries() -> dict[str, Any]:
    """GET /api/trust_guidance/entries — guidance entries."""
    try:
        data = _load_json("runtime_trust_guidance_latest.json")
        if data is None:
            return {"ok": True, "guidance_entries": [], "entry_count": 0}
        entries = data.get("guidance_entries", [])
        return {
            "ok":              True,
            "guidance_entries": entries,
            "entry_count":     len(entries),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def trust_guidance_mode() -> dict[str, Any]:
    """GET /api/trust_guidance/mode — current guidance mode."""
    try:
        data = _load_json("runtime_trust_guidance_index.json")
        if data is None:
            return {"ok": True, "guidance_mode": None, "caution_class": None}
        return {
            "ok":            True,
            "guidance_mode": data.get("guidance_mode"),
            "caution_class": data.get("caution_class"),
            "description":   _load_json("runtime_trust_guidance_latest.json",) and
                             (_load_json("runtime_trust_guidance_latest.json") or {}).get("description"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def trust_guidance_run(request: "Request") -> "JSONResponse":
    """POST /api/trust_guidance/run — trigger guidance run."""
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
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        result = run_trust_aware_guidance()
        return JSONResponse(status_code=200, content={
            "ok":               True,
            "triggered_by":     operator_id,
            "guidance_mode":    result["guidance_mode"],
            "caution_class":    result["caution_class"],
            "overall_trust_class": result["overall_trust_class"],
            "entry_count":      result["entry_count"],
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"guidance run failed: {exc}"})


def register_trust_guidance_routes(app: Any) -> None:
    """Register AG-50 routes on a FastAPI app instance."""
    app.add_api_route("/api/trust_guidance/latest",  trust_guidance_latest,  methods=["GET"])
    app.add_api_route("/api/trust_guidance/index",   trust_guidance_index,   methods=["GET"])
    app.add_api_route("/api/trust_guidance/entries", trust_guidance_entries, methods=["GET"])
    app.add_api_route("/api/trust_guidance/mode",    trust_guidance_mode,    methods=["GET"])
    app.add_api_route("/api/trust_guidance/run",     trust_guidance_run,     methods=["POST"])
