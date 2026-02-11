#!/usr/bin/env python3
"""Phase 2: RunProvenance evidence enforcement (fail-closed)."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

PROVENANCE_SCHEMA_VERSION = "run_provenance_v1"

REQUIRED_FIELDS = ("author", "tool", "input_hash", "output_hash", "ts", "evidence_refs")


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _resolve_root() -> Path:
    raw = os.environ.get("ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve(strict=False)
    return Path(__file__).resolve().parents[1]


def _provenance_log_path() -> Path:
    return _resolve_root() / "observability" / "artifacts" / "run_provenance.jsonl"


def _events_path() -> Path:
    return _resolve_root() / "observability" / "events.jsonl"


def canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def append_event(event: Dict[str, Any]) -> None:
    path = _events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(event)
    row.setdefault("ts", _utc_now())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def validate_provenance(provenance: Dict[str, Any]) -> None:
    if not isinstance(provenance, dict):
        raise RuntimeError("run_provenance_missing")
    for key in REQUIRED_FIELDS:
        if key not in provenance:
            raise RuntimeError(f"run_provenance_missing_field:{key}")
    if not isinstance(provenance.get("author"), str) or not provenance["author"].strip():
        raise RuntimeError("run_provenance_invalid_author")
    if not isinstance(provenance.get("tool"), str) or not provenance["tool"].strip():
        raise RuntimeError("run_provenance_invalid_tool")
    if not isinstance(provenance.get("evidence_refs"), list):
        raise RuntimeError("run_provenance_invalid_evidence_refs")


def init_run_provenance(base: Dict[str, Any], execution_input: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(base, dict):
        raise RuntimeError("run_provenance_missing")
    author = str(base.get("author") or "").strip()
    tool = str(base.get("tool") or "").strip()
    evidence_refs = list(base.get("evidence_refs") or [])
    if not author:
        raise RuntimeError("run_provenance_invalid_author")
    if not tool:
        raise RuntimeError("run_provenance_invalid_tool")

    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "author": author,
        "tool": tool,
        "input_hash": canonical_hash(execution_input),
        "output_hash": "",
        "ts": _utc_now(),
        "evidence_refs": evidence_refs,
    }


def complete_run_provenance(provenance: Dict[str, Any], execution_output: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(provenance)
    row["output_hash"] = canonical_hash(execution_output)
    validate_provenance(row)
    return row


def append_provenance(row: Dict[str, Any]) -> None:
    validate_provenance(row)
    path = _provenance_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_events() -> List[Dict[str, Any]]:
    path = _events_path()
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def load_provenance_rows() -> List[Dict[str, Any]]:
    path = _provenance_log_path()
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def emit_execution_verified_if_proven(actor: str = "Phase2EvidenceVerifier") -> bool:
    rows = load_provenance_rows()
    events = load_events()

    has_started = any(e.get("type") == "execution.started" for e in events)
    has_failed = any(e.get("type") == "execution.failed" for e in events)
    has_completed = any(e.get("type") == "execution.completed" for e in events)

    schema_ok = len(rows) > 0 and all(all(k in row for k in REQUIRED_FIELDS) for row in rows)

    if not (schema_ok and has_started and has_failed and has_completed):
        return False

    append_event(
        {
            "type": "execution.verified",
            "category": "execution",
            "actor": actor,
            "proof": {
                "provenance_rows": len(rows),
                "events_path": str(_events_path()),
                "provenance_path": str(_provenance_log_path()),
            },
        }
    )
    return True
