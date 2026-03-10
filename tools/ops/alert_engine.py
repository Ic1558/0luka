#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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
DEFAULT_INTERVAL_SECONDS = 5.0


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _observability_root() -> Path:
    raw = os.environ.get("LUKA_OBSERVABILITY_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_OBSERVABILITY_ROOT


def _activity_feed_path() -> Path:
    return _observability_root() / "logs" / "activity_feed.jsonl"


def _alerts_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "alerts.jsonl"


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


def load_runtime_status(*, runtime_root: Path | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["LUKA_RUNTIME_ROOT"] = str(runtime_root or _runtime_root())
    return _run_json_command([sys.executable, "tools/ops/runtime_status_report.py", "--json"], env=env)


def load_operator_status(*, runtime_root: Path | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["LUKA_RUNTIME_ROOT"] = str(runtime_root or _runtime_root())
    return _run_json_command([sys.executable, "tools/ops/operator_status_report.py", "--json"], env=env)


def load_recent_activity(limit: int = 50) -> list[dict[str, Any]]:
    path = _activity_feed_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-limit:]


def _latest_activity_suffix(activity_rows: list[dict[str, Any]]) -> str:
    if not activity_rows:
        return ""
    latest = activity_rows[-1]
    ts = latest.get("ts_utc") or latest.get("ts")
    action = latest.get("action") or latest.get("event")
    parts: list[str] = []
    if action:
        parts.append(f"last_activity={action}")
    if ts:
        parts.append(f"last_ts={ts}")
    if not parts:
        return ""
    return f" ({', '.join(parts)})"


def _alert(
    *,
    timestamp: str,
    severity: str,
    component: str,
    message: str,
) -> dict[str, str]:
    return {
        "timestamp": timestamp,
        "severity": severity,
        "component": component,
        "message": message,
        "source": "alert_engine",
    }


def _component_last_alerts(alerts_path: Path) -> dict[str, dict[str, Any]]:
    if not alerts_path.exists():
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for raw in alerts_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        component = payload.get("component")
        if isinstance(component, str):
            latest[component] = payload
    return latest


def evaluate_alerts(
    runtime_status: dict[str, Any],
    operator_status: dict[str, Any],
    activity_rows: list[dict[str, Any]],
    *,
    previous_alerts: dict[str, dict[str, Any]] | None = None,
    timestamp: str | None = None,
) -> list[dict[str, str]]:
    ts = timestamp or _utc_now()
    suffix = _latest_activity_suffix(activity_rows)
    current: dict[str, dict[str, str]] = {}

    memory_status = str(operator_status.get("memory_status", "UNAVAILABLE")).upper()
    if memory_status == "CRITICAL":
        current["memory"] = _alert(
            timestamp=ts,
            severity="CRITICAL",
            component="memory",
            message=f"memory_status=CRITICAL{suffix}",
        )

    ledger_status = str(operator_status.get("ledger_status", "UNAVAILABLE")).upper()
    if ledger_status != "VERIFIED":
        current["ledger"] = _alert(
            timestamp=ts,
            severity="CRITICAL",
            component="ledger",
            message=f"ledger_proof={ledger_status}{suffix}",
        )

    redis_status = str(operator_status.get("redis", "MISSING")).upper()
    if redis_status != "RUNNING":
        current["redis"] = _alert(
            timestamp=ts,
            severity="CRITICAL",
            component="redis",
            message=f"redis={redis_status}{suffix}",
        )

    api_status = str(operator_status.get("api_server", "MISSING")).upper()
    if api_status != "RUNNING":
        current["api"] = _alert(
            timestamp=ts,
            severity="CRITICAL",
            component="api",
            message=f"api_server={api_status}{suffix}",
        )

    bridge_status = str(operator_status.get("bridge_status", "UNAVAILABLE")).upper()
    if bridge_status != "OK":
        current["bridge"] = _alert(
            timestamp=ts,
            severity="CRITICAL",
            component="bridge",
            message=f"bridge={bridge_status}{suffix}",
        )

    runtime_overall = str(runtime_status.get("overall_status", "FAILED")).upper()
    operator_overall = str(operator_status.get("overall_status", "CRITICAL")).upper()
    if runtime_overall != "HEALTHY":
        current["runtime"] = _alert(
            timestamp=ts,
            severity="CRITICAL" if runtime_overall == "FAILED" else "WARNING",
            component="runtime",
            message=f"runtime overall_status={runtime_overall}{suffix}",
        )
    elif operator_overall != "HEALTHY":
        current["runtime"] = _alert(
            timestamp=ts,
            severity="CRITICAL" if operator_overall == "CRITICAL" else "WARNING",
            component="runtime",
            message=f"operator overall_status={operator_overall}{suffix}",
        )

    alerts = list(current.values())
    previous = previous_alerts or {}
    for component, last in previous.items():
        if component in current:
            continue
        if str(last.get("severity", "")).upper() == "INFO":
            continue
        alerts.append(
            _alert(
                timestamp=ts,
                severity="INFO",
                component=component,
                message=f"{component} recovered{suffix}",
            )
        )
    return alerts


def append_alerts(alerts_path: Path, alerts: list[dict[str, str]]) -> None:
    if not alerts:
        return
    alerts_path.parent.mkdir(parents=True, exist_ok=True)
    with alerts_path.open("a", encoding="utf-8") as handle:
        for alert in alerts:
            handle.write(json.dumps(alert, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_once(*, runtime_root: Path | None = None) -> list[dict[str, str]]:
    resolved_runtime_root = runtime_root or _runtime_root()
    runtime_status = load_runtime_status(runtime_root=resolved_runtime_root)
    operator_status = load_operator_status(runtime_root=resolved_runtime_root)
    activity_rows = load_recent_activity()
    alerts_path = _alerts_path(resolved_runtime_root)
    previous = _component_last_alerts(alerts_path)
    alerts = evaluate_alerts(runtime_status, operator_status, activity_rows, previous_alerts=previous)
    append_alerts(alerts_path, alerts)
    return alerts


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate operator alerts from existing status reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run one alert evaluation pass")
    mode.add_argument("--loop", action="store_true", help="Run alert evaluation in a loop")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS, help="Loop interval in seconds")
    args = parser.parse_args()

    try:
        if args.once:
            alerts = run_once()
            for alert in alerts:
                print(json.dumps(alert, ensure_ascii=False))
            return 0

        while True:
            alerts = run_once()
            for alert in alerts:
                print(json.dumps(alert, ensure_ascii=False))
            time.sleep(max(args.interval, 0.1))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"alert_engine_failed:{exc}"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
