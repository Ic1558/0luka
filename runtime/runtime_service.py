#!/usr/bin/env python3
"""Unified runtime service boundary for bridge/dispatcher/librarian.

This module is intentionally minimal:
- resolves runtime root without hardcoded paths
- validates TaskSpec v2 at runtime boundary (with compatibility normalization)
- appends runtime transitions to the system ledger
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.runtime.runtime_state_resolver import RuntimeStateResolver

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


KNOWN_INTENT_LANES: Dict[str, str] = {
    "cole.search_docs": "cole",
    "lisa.exec_shell": "lisa",
    "paula.run_strategy": "paula",
}

KNOWN_SERVICES = {"bridge", "dispatcher", "librarian"}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def resolve_runtime_root(runtime_root: Optional[str | Path] = None) -> Path:
    candidate = runtime_root or os.environ.get("RUNTIME_ROOT") or os.environ.get("ROOT")
    if not candidate or not str(candidate).strip():
        raise RuntimeError(
            "runtime_root_missing: provide runtime_root or env RUNTIME_ROOT/ROOT"
        )
    return Path(str(candidate)).expanduser().resolve()


@dataclass
class RuntimeService:
    runtime_root: Path
    service_name: str
    schema_v2_path: Path = field(init=False)
    system_ledger_path: Path = field(init=False)

    def __post_init__(self) -> None:
        if self.runtime_root is None:
            raise RuntimeError("runtime_root_missing")
        if not self.runtime_root.exists():
            raise RuntimeError(f"runtime_root_not_found:{self.runtime_root}")
        if self.service_name not in KNOWN_SERVICES:
            raise ValueError(f"unknown_runtime_service:{self.service_name}")
        self.schema_v2_path = self.runtime_root / "interface" / "schemas" / "task_spec_v2.yaml"
        self.system_ledger_path = (
            self.runtime_root / "observability" / "stl" / "ledger" / "global_beacon.jsonl"
        )

    @classmethod
    def create(
        cls, *, runtime_root: Optional[str | Path] = None, service_name: str
    ) -> "RuntimeService":
        return cls(runtime_root=resolve_runtime_root(runtime_root), service_name=service_name)

    def get_runtime_state_resolver(
        self, runtime_root: Optional[str | Path] = None
    ) -> RuntimeStateResolver:
        if runtime_root is not None:
            return RuntimeStateResolver.from_runtime_root(runtime_root)
        return RuntimeStateResolver(self.runtime_root)

    def validate_task_boundary(
        self, task: Dict[str, Any], *, allow_compat_v1: bool = True
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        normalized = dict(task)
        if allow_compat_v1:
            normalized = self._normalize_compat_task(normalized)

        errors: List[str] = []
        schema = self._load_taskspec_schema()
        required = schema.get("required", [])
        for key in required if isinstance(required, list) else []:
            if key not in normalized:
                errors.append(f"missing:{key}")

        operations = normalized.get("operations")
        if not isinstance(operations, list) or not operations:
            errors.append("invalid:operations")
        else:
            for index, op in enumerate(operations, start=1):
                if not isinstance(op, dict):
                    errors.append(f"invalid:operations[{index}]")
                    continue
                for key in ("id", "tool", "params"):
                    if key not in op:
                        errors.append(f"missing:operations[{index}].{key}")
                if "params" in op and not isinstance(op["params"], dict):
                    errors.append(f"invalid:operations[{index}].params")

        lane_allowed = (
            schema.get("rules", {}).get("lane", {}).get("allowed", [])
            if isinstance(schema.get("rules"), dict)
            else []
        )
        lane = normalized.get("lane")
        if not lane:
            errors.append("missing:lane")
        elif lane_allowed and lane not in lane_allowed:
            errors.append("invalid:lane")

        executor_allowed = (
            schema.get("rules", {}).get("executor", {}).get("allowed", [])
            if isinstance(schema.get("rules"), dict)
            else []
        )
        executor = normalized.get("executor")
        if not executor:
            errors.append("missing:executor")
        elif executor_allowed and executor not in executor_allowed:
            errors.append("invalid:executor")

        created_at = str(normalized.get("created_at_utc", "")).strip()
        if not created_at or not created_at.endswith("Z"):
            errors.append("invalid:created_at_utc")

        intent = str(normalized.get("intent", "")).strip()
        if intent in KNOWN_INTENT_LANES and normalized.get("lane") != KNOWN_INTENT_LANES[intent]:
            errors.append("invalid:lane_intent_mismatch")

        return (len(errors) == 0, normalized, errors)

    def record_transition(
        self, *, task_id: str, phase: str, status: str, detail: str = "", meta: Optional[Dict[str, Any]] = None
    ) -> None:
        payload = {
            "ts_utc": _utc_now(),
            "category": "runtime_transition",
            "service": self.service_name,
            "task_id": task_id,
            "phase": phase,
            "status": status,
            "detail": detail,
            "meta": meta or {},
        }
        self.system_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.system_ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _load_taskspec_schema(self) -> Dict[str, Any]:
        if yaml is None:
            return {}
        if not self.schema_v2_path.exists():
            return {}
        try:
            loaded = yaml.safe_load(self.schema_v2_path.read_text(encoding="utf-8")) or {}
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    def _normalize_compat_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(task)
        normalized.setdefault("version", 2)
        task_id = str(normalized.get("task_id") or "").strip() or "unknown-task"
        normalized["task_id"] = task_id

        if not normalized.get("created_at_utc"):
            normalized["created_at_utc"] = _utc_now()

        if not normalized.get("author"):
            author = (
                str(normalized.get("author") or "").strip()
                or str(normalized.get("actor") or "").strip()
                or str(normalized.get("origin") or "").strip()
                or "human"
            )
            normalized["author"] = author

        intent = str(normalized.get("intent") or "").strip()
        normalized["intent"] = intent

        if not normalized.get("lane"):
            normalized["lane"] = KNOWN_INTENT_LANES.get(intent) or "task"

        executor = str(normalized.get("executor") or "").strip() or "shell"
        normalized["executor"] = executor

        payload = normalized.get("payload")
        if not isinstance(payload, dict):
            payload = {}
            normalized["payload"] = payload

        operations = normalized.get("operations")
        if not isinstance(operations, list) or not operations:
            normalized["operations"] = [
                {
                    "id": f"{task_id}:op1",
                    "tool": executor,
                    "params": payload,
                }
            ]
        return normalized
