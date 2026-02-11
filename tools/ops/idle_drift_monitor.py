#!/usr/bin/env python3
"""Idle/Drift Monitor (observer-only, fail-closed)."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

FUNCTIONAL_ACTIONS = {
    "started",
    "completed",
    "verified",
    "dispatch_start",
    "dispatch_committed",
    "dispatch_rejected",
}


@dataclass(frozen=True)
class Config:
    root: Path
    source_log: Path
    report_dir: Path
    idle_threshold_sec: int
    drift_threshold_sec: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        if ts > 10**12:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if not isinstance(ts, str):
        return None
    raw = ts.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _resolve_root() -> Path:
    env_root = os.environ.get("ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve(strict=False)
    cur = Path(__file__).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            return parent
    return Path(__file__).resolve().parents[2]


def _resolve_repo_path(root: Path, raw: str) -> Path:
    val = (raw or "").strip()
    if val == "ref://activity_feed":
        val = "observability/logs/activity_feed.jsonl"
    p = Path(val).expanduser()
    if p.is_absolute():
        return p.resolve(strict=False)
    return (root / p).resolve(strict=False)


def _resolve_config() -> Config:
    root = _resolve_root()
    source_raw = os.environ.get("LUKA_ACTIVITY_FEED_JSONL", "observability/logs/activity_feed.jsonl")
    report_raw = os.environ.get("LUKA_IDLE_DRIFT_REPORT_DIR", "observability/reports/idle_drift_monitor")
    source_log = _resolve_repo_path(root, source_raw)
    report_dir = _resolve_repo_path(root, report_raw)
    idle_threshold_sec = int(os.environ.get("LUKA_IDLE_THRESHOLD_SEC", "900"))
    drift_threshold_sec = int(os.environ.get("LUKA_DRIFT_THRESHOLD_SEC", "120"))
    return Config(
        root=root,
        source_log=source_log,
        report_dir=report_dir,
        idle_threshold_sec=idle_threshold_sec,
        drift_threshold_sec=drift_threshold_sec,
    )


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), prefix=f".{path.name}.", delete=False
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _extract_ts(event: dict[str, Any]) -> Optional[datetime]:
    if "ts" in event:
        ts = _parse_iso(event.get("ts"))
        if ts is not None:
            return ts
    if "ts_utc" in event:
        ts = _parse_iso(event.get("ts_utc"))
        if ts is not None:
            return ts
    if "timestamp" in event:
        ts = _parse_iso(event.get("timestamp"))
        if ts is not None:
            return ts
    return None


def _is_heartbeat(event: dict[str, Any]) -> bool:
    action = str(event.get("action", "")).strip().lower()
    if action == "heartbeat":
        return True
    ev = str(event.get("event", "")).strip().lower()
    return "heartbeat" in ev if ev else False


def _is_functional_activity(event: dict[str, Any]) -> bool:
    action = str(event.get("action", "")).strip().lower()
    return action in FUNCTIONAL_ACTIONS


def evaluate_once(cfg: Config) -> tuple[dict[str, Any], int]:
    now = _utc_now()
    missing: list[str] = []
    events: list[dict[str, Any]] = []

    if not cfg.source_log.exists() or not os.access(cfg.source_log, os.R_OK):
        missing.append("error.log_missing_or_unreadable")
    else:
        with cfg.source_log.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = line.strip()
                if not row:
                    continue
                try:
                    payload = json.loads(row)
                except json.JSONDecodeError:
                    missing.append("error.log_parse_failure")
                    break
                if not isinstance(payload, dict):
                    missing.append("error.log_parse_failure")
                    break
                events.append(payload)

    last_activity_ts: Optional[datetime] = None
    last_heartbeat_ts: Optional[datetime] = None

    if "error.log_parse_failure" not in missing:
        for event in events:
            ts = _extract_ts(event)
            if ts is None:
                continue
            if _is_functional_activity(event):
                if last_activity_ts is None or ts > last_activity_ts:
                    last_activity_ts = ts
            if _is_heartbeat(event):
                if last_heartbeat_ts is None or ts > last_heartbeat_ts:
                    last_heartbeat_ts = ts

    if "error.log_missing_or_unreadable" not in missing and "error.log_parse_failure" not in missing:
        if last_activity_ts is None:
            missing.append("idle.system.stale")
            idle_age = None
            idle_ok = False
        else:
            idle_age = int((now - last_activity_ts).total_seconds())
            idle_ok = idle_age <= cfg.idle_threshold_sec
            if not idle_ok:
                missing.append("idle.system.stale")

        if last_heartbeat_ts is None:
            missing.append("drift.heartbeat.stale")
            drift_age = None
            drift_ok = False
        else:
            drift_age = int((now - last_heartbeat_ts).total_seconds())
            drift_ok = drift_age <= cfg.drift_threshold_sec
            if not drift_ok:
                missing.append("drift.heartbeat.stale")
    else:
        idle_age = None
        drift_age = None
        idle_ok = False
        drift_ok = False

    report = {
        "schema_version": "idle_drift_report_v1",
        "ts": _iso_utc(now),
        "source_log": str(cfg.source_log),
        "checks": {
            "idle": {
                "ok": idle_ok,
                "last_activity_ts": _iso_utc(last_activity_ts) if last_activity_ts else None,
                "age_sec": idle_age,
                "threshold_sec": cfg.idle_threshold_sec,
            },
            "drift": {
                "ok": drift_ok,
                "last_heartbeat_ts": _iso_utc(last_heartbeat_ts) if last_heartbeat_ts else None,
                "age_sec": drift_age,
                "threshold_sec": cfg.drift_threshold_sec,
            },
        },
        "missing": sorted(set(missing)),
    }

    try:
        ts_compact = now.strftime("%Y%m%dT%H%M%SZ")
        report_path = cfg.report_dir / f"{ts_compact}_idle_drift.json"
        latest_path = cfg.report_dir / "idle_drift.latest.json"
        _atomic_write(report_path, report)
        _atomic_write(latest_path, report)
    except Exception:
        report["missing"] = sorted(set(list(report.get("missing", [])) + ["error.artifact_write_failure"]))
        return report, 4

    if any(k.startswith("error.") for k in report["missing"]):
        return report, 4
    if "idle.system.stale" in report["missing"] or "drift.heartbeat.stale" in report["missing"]:
        return report, 2
    return report, 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Idle/Drift monitor (observer-only)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    cfg = _resolve_config()
    report, code = evaluate_once(cfg)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Idle/Drift report: {cfg.report_dir / 'idle_drift.latest.json'}")
        print(f"status_exit={code}")
        print(f"missing={','.join(report.get('missing', []))}")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
