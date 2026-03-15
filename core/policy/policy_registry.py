"""AG-22: Policy registry — atomic store for operator-promoted policies.

State files (under LUKA_RUNTIME_ROOT/state/):
  policy_registry.json        dict of policy_id -> policy record (atomic)
  policy_activation_log.jsonl append-only activation history

Rules:
  - Read-write by AG-22 promotion path only
  - Atomic writes (temp + os.replace)
  - plan_allowed() in policy_gate.py consults this registry
  - No auto-promotion: every entry must arrive via policy_promoter.promote()
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


_REGISTRY_NAME = "policy_registry.json"
_ACTIVATION_LOG_NAME = "policy_activation_log.jsonl"


def _state_dir() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _registry_path() -> Path:
    return _state_dir() / _REGISTRY_NAME


def load_registry() -> dict[str, Any]:
    """Return the current policy registry (policy_id → record).  Empty dict if absent."""
    p = _registry_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_registry(reg: dict[str, Any]) -> None:
    """Atomically persist the registry dict."""
    p = _registry_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def register_policy(policy_id: str, policy: dict[str, Any]) -> None:
    """Upsert one policy record into the registry."""
    reg = load_registry()
    reg[policy_id] = dict(policy, policy_id=policy_id)
    save_registry(reg)


def get_policy(policy_id: str) -> dict[str, Any] | None:
    """Return a single policy record, or None if not found."""
    return load_registry().get(policy_id)


def list_policies() -> list[dict[str, Any]]:
    """Return all promoted policies as a list."""
    return list(load_registry().values())


def remove_policy(policy_id: str) -> bool:
    """Remove a policy from the registry.  Returns True if it existed."""
    reg = load_registry()
    if policy_id not in reg:
        return False
    del reg[policy_id]
    save_registry(reg)
    return True


def append_activation_log(record: dict[str, Any]) -> None:
    """Append one activation event to the activation log (append-only)."""
    entry = dict(record)
    if not entry.get("ts"):
        entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log_path = _state_dir() / _ACTIVATION_LOG_NAME
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    tmp = log_path.with_suffix(".tmp")
    tmp.write_text(existing + json.dumps(entry) + "\n", encoding="utf-8")
    os.replace(tmp, log_path)


def list_activation_log(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent activation log entries."""
    log_path = _state_dir() / _ACTIVATION_LOG_NAME
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records[-limit:]
