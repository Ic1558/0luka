#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import approval_write

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
PRESETS: dict[str, dict[str, bool]] = {
    "memory_only": {"memory_recovery": True},
    "worker_only": {"worker_recovery": True},
    "safe_local_ops": {"memory_recovery": True, "worker_recovery": True},
    "manual_only": {},
}
LANE_ORDER = ("memory_recovery", "worker_recovery", "api_recovery", "redis_recovery")


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _approval_actions_log_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "approval_actions.jsonl"


def _validate_preset_name(name: str) -> None:
    if name not in PRESETS:
        raise RuntimeError(f"unknown_preset:{name}")


def _load_preset_history(runtime_root: Path) -> dict[str, str | None]:
    last_seen: dict[str, str | None] = {name: None for name in PRESETS}
    path = _approval_actions_log_path(runtime_root)
    if not path.exists():
        return last_seen
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        actor = str(row.get("actor") or "")
        if not actor.startswith("preset:"):
            continue
        preset_name = actor.split(":", 1)[1].strip()
        if preset_name in last_seen:
            last_seen[preset_name] = str(row.get("timestamp") or None)
    return last_seen


def list_presets(*, runtime_root: Path | None = None) -> dict[str, Any]:
    resolved_runtime_root = runtime_root or _runtime_root()
    history = _load_preset_history(resolved_runtime_root)
    presets: list[dict[str, Any]] = []
    for name in PRESETS:
        mapping = PRESETS[name]
        presets.append(
            {
                "name": name,
                "lanes": [lane for lane in LANE_ORDER if mapping.get(lane, False)],
                "last_applied_at": history.get(name),
            }
        )
    return {"ok": True, "runtime_root": str(resolved_runtime_root), "presets": presets}


def apply_preset(*, preset: str, runtime_root: Path | None = None) -> dict[str, Any]:
    _validate_preset_name(preset)
    resolved_runtime_root = runtime_root or _runtime_root()
    mapping = PRESETS[preset]
    actor = f"preset:{preset}"
    results: list[dict[str, Any]] = []
    for lane in LANE_ORDER:
        if not mapping.get(lane, False):
            continue
        results.append(
            approval_write.write_approval_action(
                lane=lane,
                actor=actor,
                approve=True,
                runtime_root=resolved_runtime_root,
            )
        )
    return {
        "ok": True,
        "action": "apply",
        "preset": preset,
        "actor": actor,
        "lanes": [lane for lane in LANE_ORDER if mapping.get(lane, False)],
        "results": results,
    }


def reset_preset(*, preset: str, runtime_root: Path | None = None) -> dict[str, Any]:
    _validate_preset_name(preset)
    resolved_runtime_root = runtime_root or _runtime_root()
    mapping = PRESETS[preset]
    actor = f"preset:{preset}"
    results: list[dict[str, Any]] = []
    for lane in LANE_ORDER:
        if not mapping.get(lane, False):
            continue
        results.append(
            approval_write.write_approval_action(
                lane=lane,
                actor=actor,
                revoke=True,
                runtime_root=resolved_runtime_root,
            )
        )
    return {
        "ok": True,
        "action": "reset",
        "preset": preset,
        "actor": actor,
        "lanes": [lane for lane in LANE_ORDER if mapping.get(lane, False)],
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="List/apply/reset deterministic approval presets.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--apply", metavar="PRESET")
    parser.add_argument("--reset", metavar="PRESET")
    args = parser.parse_args()

    chosen = sum(bool(flag) for flag in (args.list, bool(args.apply), bool(args.reset)))
    if chosen != 1:
        payload = {"ok": False, "errors": ["select_exactly_one_action"]}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    try:
        if args.list:
            payload = list_presets()
        elif args.apply:
            payload = apply_preset(preset=args.apply)
        else:
            payload = reset_preset(preset=args.reset)
    except Exception as exc:
        payload = {"ok": False, "errors": [str(exc)]}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
