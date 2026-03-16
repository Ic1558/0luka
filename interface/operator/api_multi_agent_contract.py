"""AG-71: Multi-Agent Execution Contract API."""
from __future__ import annotations
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass


async def contract_latest(request: Request) -> JSONResponse:
    from runtime.multi_agent_contract import get_contract_latest
    d = get_contract_latest()
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)


async def contract_index(request: Request) -> JSONResponse:
    from runtime.multi_agent_contract import list_contracts
    return JSONResponse({"contracts": list_contracts()})


async def contract_register(request: Request) -> JSONResponse:
    try:
        task = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
    try:
        from runtime.multi_agent_contract import register_contract_task
        record = register_contract_task(task)
        return JSONResponse({"ok": record["valid"], "contract_id": record["contract_id"], "record": record})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def register_multi_agent_contract_routes(app: Any) -> None:
    app.add_api_route("/api/multi_agent_contract/latest", contract_latest, methods=["GET"])
    app.add_api_route("/api/multi_agent_contract/index", contract_index, methods=["GET"])
    app.add_api_route("/api/multi_agent_contract/register", contract_register, methods=["POST"])
