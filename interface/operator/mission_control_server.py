#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path
from string import Template
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    from starlette.applications import Starlette as FastAPI
    from starlette.responses import HTMLResponse, JSONResponse
    FASTAPI_AVAILABLE = False

from starlette.routing import Route

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
CANONICAL_OBSERVABILITY_ROOT = Path("/Users/icmini/0luka/observability")
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7010
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "mission_control.html"


def _observability_root() -> Path:
    raw = os.environ.get("LUKA_OBSERVABILITY_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_OBSERVABILITY_ROOT


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _activity_feed_path() -> Path:
    return _observability_root() / "logs" / "activity_feed.jsonl"


def _alerts_path() -> Path:
    return _runtime_root() / "state" / "alerts.jsonl"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{path}")
    return payload


def _run_json_command(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    stream = proc.stdout.strip() or proc.stderr.strip()
    if not stream:
        raise RuntimeError(f"empty_output:{' '.join(args)}")
    payload = json.loads(stream)
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{' '.join(args)}")
    return payload


def load_operator_status() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/operator_status_report.py", "--json"])


def load_runtime_status() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/runtime_status_report.py", "--json"])


def load_activity_entries(limit: int = 50) -> list[dict[str, Any]]:
    path = _activity_feed_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def load_alerts(limit: int = 100) -> list[dict[str, Any]]:
    path = _alerts_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def _epoch_id(runtime_status: dict[str, Any]) -> str:
    proof = runtime_status.get("proof_pack")
    if isinstance(proof, dict):
        epoch = proof.get("epoch_id")
        if epoch is not None:
            return str(epoch)
    return "n/a"


def _activity_html(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "<li>No activity available</li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        ts = escape(str(row.get("ts_utc") or row.get("ts") or "n/a"))
        action = escape(str(row.get("action") or row.get("event") or "unknown"))
        items.append(f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span></li>")
    return "\n".join(items)


def _alerts_html(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "<li class=\"alert-item info\"><span class=\"severity\">INFO</span><span class=\"component\">alerts</span><span class=\"message\">No alerts available</span></li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        severity = escape(str(row.get("severity") or "INFO")).lower()
        ts = escape(str(row.get("timestamp") or "n/a"))
        component = escape(str(row.get("component") or "unknown"))
        message = escape(str(row.get("message") or ""))
        items.append(
            "<li class=\"alert-item {severity}\">"
            "<span class=\"ts\">{ts}</span>"
            "<span class=\"severity\">{sev}</span>"
            "<span class=\"component\">{component}</span>"
            "<span class=\"message\">{message}</span>"
            "</li>".format(
                severity=severity,
                ts=ts,
                sev=escape(str(row.get("severity") or "INFO")),
                component=component,
                message=message,
            )
        )
    return "\n".join(items)


def render_mission_control(
    operator_status: dict[str, Any],
    runtime_status: dict[str, Any],
    activity_entries: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> str:
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    details = operator_status.get("details") if isinstance(operator_status.get("details"), dict) else {}
    bridge = details.get("bridge_checks") if isinstance(details.get("bridge_checks"), dict) else {}
    return template.safe_substitute(
        system_health=escape(str(runtime_status.get("system_health", {}).get("status", "FAILED"))),
        ledger_status=escape(str(operator_status.get("ledger_status", "FAILED"))),
        epoch_id=escape(_epoch_id(runtime_status)),
        operator_overall=escape(str(operator_status.get("overall_status", "UNKNOWN"))),
        memory_status=escape(str(operator_status.get("memory_status", "UNAVAILABLE"))),
        api_server=escape(str(operator_status.get("api_server", "MISSING"))),
        redis=escape(str(operator_status.get("redis", "MISSING"))),
        bridge_consumer=escape(str(bridge.get("consumer", "unavailable"))),
        bridge_inflight=escape(str(bridge.get("inflight", "unavailable"))),
        bridge_outbox=escape(str(bridge.get("outbox", "unavailable"))),
        activity_items=_activity_html(activity_entries),
        alert_items=_alerts_html(alerts),
    )


async def health_endpoint(request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "mission_control", "port": SERVER_PORT})


async def operator_status_endpoint(request) -> JSONResponse:
    return JSONResponse(load_operator_status())


async def runtime_status_endpoint(request) -> JSONResponse:
    return JSONResponse(load_runtime_status())


async def activity_endpoint(request) -> JSONResponse:
    return JSONResponse(load_activity_entries())


async def alerts_endpoint(request) -> JSONResponse:
    limit_raw = request.query_params.get("limit", "100")
    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 100
    return JSONResponse({"alerts": load_alerts(limit=limit)})


async def root_endpoint(request) -> HTMLResponse:
    operator_status = load_operator_status()
    runtime_status = load_runtime_status()
    activity_entries = load_activity_entries()
    alerts = load_alerts()
    return HTMLResponse(render_mission_control(operator_status, runtime_status, activity_entries, alerts))


def create_app():
    if FASTAPI_AVAILABLE:
        app = FastAPI(title="0luka Mission Control", version="0.1.0")
        app.add_api_route("/health", health_endpoint, methods=["GET"])
        app.add_api_route("/api/operator_status", operator_status_endpoint, methods=["GET"])
        app.add_api_route("/api/runtime_status", runtime_status_endpoint, methods=["GET"])
        app.add_api_route("/api/activity", activity_endpoint, methods=["GET"])
        app.add_api_route("/api/alerts", alerts_endpoint, methods=["GET"])
        app.add_api_route("/", root_endpoint, methods=["GET"], response_class=HTMLResponse)
        return app

    return FastAPI(
        routes=[
            Route("/health", health_endpoint),
            Route("/api/operator_status", operator_status_endpoint),
            Route("/api/runtime_status", runtime_status_endpoint),
            Route("/api/activity", activity_endpoint),
            Route("/api/alerts", alerts_endpoint),
            Route("/", root_endpoint),
        ]
    )


app = create_app()


def main() -> int:
    import uvicorn

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
