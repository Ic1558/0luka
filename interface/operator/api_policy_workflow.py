"""AG-66: Policy Workflow API."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass


def _state_dir():
    return Path(os.environ.get("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")) / "state"

def _load(f):
    p = _state_dir() / f
    return json.loads(p.read_text()) if p.exists() else None


async def workflow_latest(request: Request) -> JSONResponse:
    d = _load("runtime_policy_workflow_latest.json")
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)

async def workflow_index(request: Request) -> JSONResponse:
    return JSONResponse({"workflows": _load("runtime_policy_workflow_index.json") or []})

async def workflow_run_review(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid JSON"}, status_code=400)
    policy_id = body.get("policy_id", "test_policy")
    operator_id = body.get("operator_id", "unknown")
    try:
        from runtime.policy_workflow_hardening import run_review
        return JSONResponse(run_review(policy_id, operator_id))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def register_policy_workflow_routes(app: Any) -> None:
    app.add_api_route("/api/policy_workflow/latest", workflow_latest, methods=["GET"])
    app.add_api_route("/api/policy_workflow/index", workflow_index, methods=["GET"])
    app.add_api_route("/api/policy_workflow/run_review", workflow_run_review, methods=["POST"])
