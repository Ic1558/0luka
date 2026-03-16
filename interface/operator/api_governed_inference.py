"""AG-70: Governed Inference Fabric API."""
from __future__ import annotations
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass


async def inference_latest(request: Request) -> JSONResponse:
    from runtime.governed_inference import get_inference_latest
    d = get_inference_latest()
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)


async def inference_index(request: Request) -> JSONResponse:
    from runtime.governed_inference import list_inference_requests
    return JSONResponse({"requests": list_inference_requests()})


async def inference_route(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    prompt = body.get("prompt", "")
    if not prompt:
        return JSONResponse({"ok": False, "error": "prompt_required"}, status_code=400)
    try:
        from runtime.governed_inference import route_inference
        record = route_inference(
            prompt=prompt,
            preferred_provider=body.get("provider"),
            operator_id=body.get("operator_id", "system"),
            routing_hint=body.get("routing_hint", "cost"),
        )
        return JSONResponse({"ok": True, "request_id": record["request_id"], "record": record})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def register_governed_inference_routes(app: Any) -> None:
    app.add_api_route("/api/governed_inference/latest", inference_latest, methods=["GET"])
    app.add_api_route("/api/governed_inference/index", inference_index, methods=["GET"])
    app.add_api_route("/api/governed_inference/route", inference_route, methods=["POST"])
