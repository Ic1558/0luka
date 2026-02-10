#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import unquote, urlparse

try:
    from jsonschema import ValidationError, validate
except ImportError:
    ValidationError = Exception  # type: ignore[assignment]
    validate = None

from core.ref_resolver import host_fingerprint, resolve_ref
from core.verify.no_hardpath_guard import find_hardpath_violations

ROOT = Path(os.environ.get("ROOT") or Path(__file__).resolve().parents[1])
SCHEMA_PATH = ROOT / "interface/schemas/0luka_result_envelope_v1.json"
DEFAULT_OUTBOX_REF = "ref://interface/outbox"


class OutboxWriterError(RuntimeError):
    pass


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _json_hash(data: Any) -> str:
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _to_file_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise OutboxWriterError(f"unsupported_uri_scheme:{parsed.scheme}")
    return Path(unquote(parsed.path))


def _load_schema(path: Path) -> Dict[str, Any]:
    if validate is None:
        raise OutboxWriterError("missing dependency: jsonschema (pip install jsonschema)")
    if not path.exists():
        raise OutboxWriterError(f"schema_not_found:{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OutboxWriterError(f"invalid_schema_json:{exc}") from exc
    if not isinstance(data, dict):
        raise OutboxWriterError("invalid_schema_root")
    return data


def _ensure_result_envelope(result: Dict[str, Any]) -> Dict[str, Any]:
    task_id = str(result.get("task_id", "")).strip()
    status = str(result.get("status", "")).strip()
    if not task_id:
        raise OutboxWriterError("missing_task_id")
    if not status:
        raise OutboxWriterError("missing_status")

    outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
    artifacts = outputs.get("artifacts") if isinstance(outputs.get("artifacts"), list) else []
    outputs_json = outputs.get("json") if isinstance(outputs.get("json"), dict) else {}

    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    logs = evidence.get("logs") if isinstance(evidence.get("logs"), list) else []
    commands = evidence.get("commands") if isinstance(evidence.get("commands"), list) else []

    started_at = str(result.get("started_at") or result.get("ts_utc") or _utc_now())
    ended_at = _utc_now()

    envelope = {
        "v": "0luka.result/v1",
        "type": "task.result",
        "task_id": task_id,
        "status": status,
        "summary": str(result.get("summary") or ""),
        "outputs": {"json": outputs_json, "artifacts": artifacts},
        "evidence": {"logs": logs, "commands": commands},
        "provenance": {
            "trace_id": str(result.get("trace_id") or task_id),
            "started_at": started_at,
            "ended_at": ended_at,
            "engine": {"name": "core", "version": "phase1e", "host": host_fingerprint()},
            "hashes": {
                "inputs_sha256": str(
                    (((result.get("provenance") or {}).get("hashes") or {}).get("inputs_sha256"))
                    or _json_hash(result.get("inputs", {}))
                ),
                "outputs_sha256": str(
                    (((result.get("provenance") or {}).get("hashes") or {}).get("outputs_sha256"))
                    or _json_hash({"outputs": outputs_json, "artifacts": artifacts})
                ),
            },
        },
    }

    # Policy for 1E: ok + no logs/commands -> partial
    if envelope["status"] == "ok" and not logs and not commands:
        envelope["status"] = "partial"
        envelope["summary"] = envelope["summary"] or "missing evidence for ok result"
    return envelope


def _to_error_envelope(task_id: str, reason: str) -> Dict[str, Any]:
    now = _utc_now()
    return {
        "v": "0luka.result/v1",
        "type": "task.result",
        "task_id": task_id,
        "status": "error",
        "summary": reason,
        "outputs": {"json": {}, "artifacts": []},
        "evidence": {"logs": [], "commands": []},
        "provenance": {
            "trace_id": task_id,
            "started_at": now,
            "ended_at": now,
            "engine": {"name": "core", "version": "phase1e", "host": host_fingerprint()},
            "hashes": {"inputs_sha256": _json_hash({}), "outputs_sha256": _json_hash({})},
        },
    }


def _validate_envelope(envelope: Dict[str, Any]) -> None:
    schema = _load_schema(SCHEMA_PATH)
    try:
        validate(instance=envelope, schema=schema)
    except ValidationError as exc:
        raise OutboxWriterError(f"schema_validation_failed:{exc.message}") from exc


def _write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.stem}.tmp"
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_result_to_outbox(
    result: Dict[str, Any],
    *,
    outbox_ref: str = DEFAULT_OUTBOX_REF,
    ref_map_path: str | None = None,
) -> Tuple[Path, Dict[str, Any]]:
    envelope = _ensure_result_envelope(result)
    leaks = find_hardpath_violations(envelope)
    if leaks:
        reason = f"hardpath_detected:{leaks[0]['path']}:{leaks[0]['rule']}"
        envelope = _to_error_envelope(envelope["task_id"], reason)
    _validate_envelope(envelope)
    # assert-scan after normalization/redaction
    leaks_after = find_hardpath_violations(envelope)
    if leaks_after:
        raise OutboxWriterError(f"hardpath_detected_after_sanitize:{leaks_after[0]['path']}")

    override = os.environ.get("OUTBOX_ROOT", "").strip()
    if override:
        outbox_root = Path(override).expanduser().resolve(strict=False)
    else:
        resolved = resolve_ref(outbox_ref, map_path=ref_map_path)
        outbox_root = _to_file_path(str(resolved.get("uri", "")))
    out_dir = outbox_root if outbox_root.name == "tasks" else outbox_root / "tasks"
    out_path = out_dir / f"{envelope['task_id']}.result.json"
    _write_atomic(out_path, envelope)
    return out_path, envelope
