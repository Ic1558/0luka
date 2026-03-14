"""AG Bridge HTTP server - local isolation boundary between Antigravity and 0luka."""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bridge.ag_bridge import AgBridgeResponse, dispatch  # noqa: E402

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7020
RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW_SEC = 60
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "interface" / "schemas" / "ag_bridge_request_v1.yaml"

app = FastAPI(title="AG Bridge Server", version="1.0")

_schema: dict[str, Any] | None = None
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def _get_schema() -> dict[str, Any]:
    global _schema
    if _schema is None:
        loaded = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8")) or {}
        _schema = loaded if isinstance(loaded, dict) else {}
    return _schema


def _check_rate(ip: str) -> bool:
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_MAX:
        return False
    bucket.append(now)
    return True


def _token_configured() -> bool:
    return bool(os.environ.get("AG_BRIDGE_TOKEN"))


def _validate_token(request: Request) -> bool:
    expected = os.environ.get("AG_BRIDGE_TOKEN", "")
    if not expected:
        return False
    return request.headers.get("X-Bridge-Token", "") == expected


@app.get("/api/bridge/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "ag_bridge", "port": SERVER_PORT})


@app.post("/api/bridge/dispatch")
async def bridge_dispatch(request: Request) -> JSONResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate(client_ip):
        return JSONResponse({"error": "rate_limit_exceeded"}, status_code=429)

    if not _token_configured():
        return JSONResponse({"error": "bridge_token_not_configured"}, status_code=503)
    if not _validate_token(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        jsonschema.validate(instance=body, schema=_get_schema())
    except jsonschema.ValidationError as exc:
        return JSONResponse(
            {"error": "schema_invalid", "detail": exc.message},
            status_code=422,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": "schema_load_error", "detail": str(exc)},
            status_code=500,
        )

    result: AgBridgeResponse = dispatch(body)
    status_map = {"accepted": 202, "rejected": 400, "blocked": 503}
    return JSONResponse(
        {
            "request_id": result.request_id,
            "status": result.status,
            "task_id": result.task_id,
            "error": result.error,
            "policy_blocked": result.policy_blocked,
        },
        status_code=status_map.get(result.status, 400),
    )


if __name__ == "__main__":
    import uvicorn

    if not _token_configured():
        print("[bridge_server] warning: AG_BRIDGE_TOKEN is not configured; dispatch will return 503")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)

