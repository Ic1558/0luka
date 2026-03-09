#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
CANONICAL_OBSERVABILITY_ROOT = Path("/Users/icmini/0luka/observability")
API_PORT = 7001
REDIS_PORT = 6379


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _telemetry_dir() -> Path:
    raw = os.environ.get("LUKA_OBSERVABILITY_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve() / "telemetry"
    return CANONICAL_OBSERVABILITY_ROOT / "telemetry"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{path}")
    return payload


def _run_json_command(args: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    stream = proc.stdout.strip() or proc.stderr.strip()
    if not stream:
        raise RuntimeError(f"empty_output:{' '.join(args)}")
    payload = json.loads(stream)
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{' '.join(args)}")
    payload["_returncode"] = proc.returncode
    return payload


def _read_optional_telemetry(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not path.exists():
        return None, {"error": "telemetry_missing", "path": str(path)}
    try:
        return _read_json(path), None
    except Exception as exc:
        return None, {"error": f"telemetry_invalid:{exc}", "path": str(path)}


def _port_running(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _memory_status(ram_payload: dict[str, Any] | None) -> str:
    if ram_payload is None:
        return "UNAVAILABLE"
    decision = ram_payload.get("decision") if isinstance(ram_payload.get("decision"), dict) else {}
    pressure = str(ram_payload.get("pressure_level", "")).upper()
    if (
        pressure == "CRITICAL"
        or bool(decision.get("high_swap_activity"))
        or bool(decision.get("composite_critical"))
        or bool(decision.get("latch_active"))
    ):
        return "CRITICAL"
    if pressure and pressure not in {"NORMAL", "OK"}:
        return "DEGRADED"
    return "OK"


def _bridge_status(
    consumer_payload: dict[str, Any] | None,
    watchdog_payload: dict[str, Any] | None,
) -> str:
    if consumer_payload is None or watchdog_payload is None:
        return "UNAVAILABLE"
    watchdog_ok = str(watchdog_payload.get("overall_status", "")).lower() == "ok"
    consumer_status = str(consumer_payload.get("status", "")).lower()
    if watchdog_ok and consumer_status in {"idle", "ok", "running"}:
        return "OK"
    return "FAILED"


def _ledger_status(runtime_payload: dict[str, Any]) -> str:
    proof = runtime_payload.get("proof_pack") if isinstance(runtime_payload.get("proof_pack"), dict) else {}
    watchdog = runtime_payload.get("ledger_watchdog") if isinstance(runtime_payload.get("ledger_watchdog"), dict) else {}
    if not proof.get("available"):
        return "UNAVAILABLE"
    if bool(proof.get("ok")) and bool(watchdog.get("ok")):
        return "VERIFIED"
    return "FAILED"


def _overall_status(
    *,
    system_health_status: str,
    api_running: bool,
    redis_running: bool,
    memory_status: str,
    bridge_status: str,
    ledger_status: str,
    telemetry_errors: list[dict[str, Any]],
) -> str:
    if system_health_status != "HEALTHY":
        return "CRITICAL"
    if not api_running or not redis_running:
        return "CRITICAL"
    if memory_status in {"CRITICAL", "DEGRADED"}:
        return "DEGRADED"
    if telemetry_errors:
        return "DEGRADED"
    if bridge_status != "OK":
        return "DEGRADED"
    if ledger_status != "VERIFIED":
        return "DEGRADED"
    return "HEALTHY"


def build_operator_status_report() -> dict[str, Any]:
    runtime_root = _runtime_root()
    env = os.environ.copy()
    env["LUKA_RUNTIME_ROOT"] = str(runtime_root)

    runtime_payload = _run_json_command([sys.executable, "tools/ops/runtime_status_report.py", "--json"])
    health_payload = _run_json_command([sys.executable, "core/health.py", "--full", "--json"], env=env)

    telemetry_root = _telemetry_dir()
    ram_payload, ram_error = _read_optional_telemetry(telemetry_root / "ram_monitor.latest.json")
    consumer_payload, consumer_error = _read_optional_telemetry(telemetry_root / "bridge_consumer.latest.json")
    watchdog_payload, bridge_watchdog_error = _read_optional_telemetry(telemetry_root / "bridge_watchdog.latest.json")

    api_running = _port_running(API_PORT)
    redis_running = _port_running(REDIS_PORT)

    system_health_status = str(runtime_payload.get("system_health", {}).get("status", "FAILED"))
    ledger_status = _ledger_status(runtime_payload)
    memory_status = _memory_status(ram_payload)
    bridge_status = _bridge_status(consumer_payload, watchdog_payload)

    telemetry_errors = [
        item
        for item in (ram_error, consumer_error, bridge_watchdog_error)
        if isinstance(item, dict)
    ]
    overall_status = _overall_status(
        system_health_status=system_health_status,
        api_running=api_running,
        redis_running=redis_running,
        memory_status=memory_status,
        bridge_status=bridge_status,
        ledger_status=ledger_status,
        telemetry_errors=telemetry_errors,
    )

    bridge_checks = watchdog_payload.get("checks") if isinstance(watchdog_payload, dict) and isinstance(watchdog_payload.get("checks"), dict) else {}

    errors: list[dict[str, Any]] = []
    errors.extend(telemetry_errors)
    if not api_running:
        errors.append({"error": "api_server_missing", "port": API_PORT})
    if not redis_running:
        errors.append({"error": "redis_missing", "port": REDIS_PORT})

    system_health = health_payload.get("status")
    if isinstance(system_health, str):
        system_health = system_health.upper()
    else:
        system_health = "FAILED"

    return {
        "ok": True,
        "overall_status": overall_status,
        "system_health": system_health,
        "ledger_status": ledger_status,
        "bridge_status": bridge_status,
        "memory_status": memory_status,
        "api_server": "RUNNING" if api_running else "MISSING",
        "redis": "RUNNING" if redis_running else "MISSING",
        "timestamp": _utc_now(),
        "details": {
            "runtime_status": runtime_payload,
            "system_health": health_payload,
            "ram_monitor": ram_payload,
            "bridge_consumer": consumer_payload,
            "bridge_watchdog": watchdog_payload,
            "bridge_checks": {
                "consumer": consumer_payload.get("status") if isinstance(consumer_payload, dict) else "unavailable",
                "inflight": bridge_checks.get("inflight", {}).get("status") if isinstance(bridge_checks.get("inflight"), dict) else "unavailable",
                "outbox": bridge_checks.get("outbox", {}).get("status") if isinstance(bridge_checks.get("outbox"), dict) else "unavailable",
            },
        },
        "errors": errors,
    }


def render_operator_status_report(report: dict[str, Any]) -> str:
    details = report.get("details") if isinstance(report.get("details"), dict) else {}
    bridge_checks = details.get("bridge_checks") if isinstance(details.get("bridge_checks"), dict) else {}
    ram_payload = details.get("ram_monitor") if isinstance(details.get("ram_monitor"), dict) else {}
    decision = ram_payload.get("decision") if isinstance(ram_payload.get("decision"), dict) else {}
    lines = [
        "Operator Runtime Status",
        "-----------------------",
        f"System Health: {report.get('system_health', 'FAILED')}",
        f"Ledger Proof: {report.get('ledger_status', 'FAILED')}",
        f"Bridge Status: {report.get('bridge_status', 'UNAVAILABLE')}",
        f"RAM Pressure: {report.get('memory_status', 'UNAVAILABLE')}",
        f"API Server: {report.get('api_server', 'MISSING')} ({API_PORT})",
        f"Redis: {report.get('redis', 'MISSING')} ({REDIS_PORT})",
        "",
        "Bridge",
        f"consumer: {bridge_checks.get('consumer', 'unavailable')}",
        f"inflight: {bridge_checks.get('inflight', 'unavailable')}",
        f"outbox: {bridge_checks.get('outbox', 'unavailable')}",
        "",
        "Memory",
        f"high_swap_activity: {bool(decision.get('high_swap_activity')) if decision else 'n/a'}",
        f"latch_active: {bool(decision.get('latch_active')) if decision else 'n/a'}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate operator-facing runtime telemetry.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    try:
        report = build_operator_status_report()
    except Exception as exc:
        payload = {
            "ok": False,
            "overall_status": "CRITICAL",
            "system_health": "FAILED",
            "ledger_status": "FAILED",
            "bridge_status": "UNAVAILABLE",
            "memory_status": "UNAVAILABLE",
            "api_server": "MISSING",
            "redis": "MISSING",
            "timestamp": _utc_now(),
            "errors": [{"error": f"report_generation_failed:{exc}"}],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(render_operator_status_report(payload))
        return 4

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(render_operator_status_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
