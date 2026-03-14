"""Read active runtime policy from core/policy.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ActivePolicy:
    version: str
    updated_at: str
    freeze_state: bool
    max_task_size_bytes: int
    deny_by_default: bool


def _default_policy_path() -> Path:
    return Path(__file__).resolve().parents[1] / "policy.yaml"


def get_active_policy(policy_path: Optional[Path] = None) -> ActivePolicy:
    path = Path(policy_path) if policy_path is not None else _default_policy_path()
    if not path.exists():
        raise RuntimeError("policy_file_missing")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("policy_parse_error")
        defaults = payload.get("defaults")
        if not isinstance(defaults, dict):
            raise RuntimeError("policy_parse_error")
        return ActivePolicy(
            version=str(payload["version"]),
            updated_at=str(payload["updated_at"]),
            freeze_state=bool(defaults["freeze_state"]),
            max_task_size_bytes=int(defaults["max_task_size_bytes"]),
            deny_by_default=bool(defaults["deny_by_default"]),
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("policy_parse_error") from exc

