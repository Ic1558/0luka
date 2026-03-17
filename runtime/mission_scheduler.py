"""AG-P10: Mission Scheduler — autonomous recurring mission dispatch.

Registry: LUKA_RUNTIME_ROOT/state/missions_registry.json
  [{
      "mission_id":      str,              # unique, e.g. "daily_status"
      "schedule":        str,              # "daily" | "hourly" | "weekly"
      "prompt":          str,              # operator prompt
      "operator_id":     str,              # default "boss"
      "provider":        str,              # default "claude"
      "notify":          bool,             # send Telegram on completion
      "enabled":         bool,             # false = skip
      "last_run_window": str | null,       # ISO window key of last successful run
  }]

Idempotency: each schedule maps to a window key (date for daily, hour for hourly,
week for weekly). If last_run_window == current window → skip (already ran).

Evidence per run:
  state/scheduled_run_latest.json
  state/scheduled_run_log.jsonl
  observability/artifacts/missions/<mission_id>_<window>.json  (via run_mission)
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


# ──────────────────────────────────────────
# Paths
# ──────────────────────────────────────────

def _runtime_root() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    return Path(rt)


def _state_dir() -> Path:
    d = _runtime_root() / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _registry_path() -> Path:
    return _state_dir() / "missions_registry.json"


# ──────────────────────────────────────────
# Registry I/O
# ──────────────────────────────────────────

def load_registry() -> list[dict]:
    """Load the missions registry. Returns [] if missing."""
    p = _registry_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_registry(missions: list[dict]) -> None:
    """Atomically write the missions registry."""
    p = _registry_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(missions, indent=2))
    tmp.replace(p)


def upsert_mission(mission: dict) -> None:
    """Insert or replace a mission in the registry by mission_id."""
    missions = load_registry()
    mid = mission["mission_id"]
    missions = [m for m in missions if m["mission_id"] != mid]
    missions.append(mission)
    save_registry(missions)


# ──────────────────────────────────────────
# Window key (idempotency)
# ──────────────────────────────────────────

def window_key(schedule: str, ts: datetime | None = None) -> str:
    """Return the current window identifier for a schedule.

    daily  → "2026-03-17"
    hourly → "2026-03-17T14"
    weekly → "2026-W11"
    """
    if ts is None:
        ts = datetime.now(timezone.utc)
    if schedule == "daily":
        return ts.strftime("%Y-%m-%d")
    if schedule == "hourly":
        return ts.strftime("%Y-%m-%dT%H")
    if schedule == "weekly":
        year, week, _ = ts.isocalendar()
        return f"{year}-W{week:02d}"
    # unknown schedule → treat as daily
    return ts.strftime("%Y-%m-%d")


# ──────────────────────────────────────────
# Evidence persistence
# ──────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


# ──────────────────────────────────────────
# Core dispatch
# ──────────────────────────────────────────

def _dispatch_mission(mission: dict, window: str) -> dict:
    """Run one mission via tools/ops/run_mission.py path."""
    mission_id = f"{mission['mission_id']}_{window}"
    try:
        from tools.ops.run_mission import run_mission
        result = run_mission(
            mission["prompt"],
            operator_id=mission.get("operator_id", "boss"),
            provider=mission.get("provider", "claude"),
            mission_id=mission_id,
            notify=mission.get("notify", False),
        )
        return result
    except Exception as exc:
        return {
            "mission_id": mission_id,
            "status": "error",
            "error": str(exc)[:300],
            "ts_end": _now(),
        }


# ──────────────────────────────────────────
# Scheduler tick
# ──────────────────────────────────────────

def tick() -> list[dict]:
    """Check all enabled missions; dispatch those due in the current window.

    Returns a list of run records (one per dispatched mission).
    Idempotent: calling tick() multiple times in the same window is safe.
    """
    now = datetime.now(timezone.utc)
    sd = _state_dir()
    missions = load_registry()
    dispatched: list[dict] = []

    for mission in missions:
        if not mission.get("enabled", False):
            continue

        schedule = mission.get("schedule", "daily")
        mid = mission["mission_id"]
        current_window = window_key(schedule, now)
        last_window = mission.get("last_run_window")

        if last_window == current_window:
            # Already ran this window — skip (idempotent)
            continue

        # Dispatch
        result = _dispatch_mission(mission, current_window)
        status = result.get("status", "unknown")

        run_record = {
            "mission_id": mid,
            "schedule": schedule,
            "window": current_window,
            "dispatched_at": _now(),
            "status": status,
            "task_id": result.get("task_id"),
            "inference_id": result.get("inference_id"),
            "artifact_path": result.get("artifact_path"),
            "error": result.get("error"),
        }

        # Update last_run_window on success (executed or partial)
        if status in ("executed", "error"):
            mission["last_run_window"] = current_window

        _append_jsonl(sd / "scheduled_run_log.jsonl", run_record)
        _atomic_write(sd / "scheduled_run_latest.json", run_record)
        dispatched.append(run_record)

    # Persist updated last_run_window values
    if dispatched:
        save_registry(missions)

    return dispatched


# ──────────────────────────────────────────
# CLI entry point (used by launchd)
# ──────────────────────────────────────────

def main() -> None:
    import sys
    # Allow running as a module: python3 -m runtime.mission_scheduler
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")

    results = tick()
    print(json.dumps({"tick_ts": _now(), "dispatched": len(results), "results": results}, indent=2))


if __name__ == "__main__":
    main()
