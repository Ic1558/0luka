#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict


class QSRuntimeStateError(RuntimeError):
    pass


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path("/Users/icmini/0luka_runtime")


def _runs_dir(runtime_root: Path | None = None) -> Path:
    resolved = runtime_root or _runtime_root()
    return resolved / "state" / "qs_runs"


def _repo_root() -> Path:
    raw = os.environ.get("ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _validate_run_id(run_id: str) -> str:
    value = str(run_id or "").strip()
    if not value:
        raise QSRuntimeStateError("qs_runtime_state_invalid:run_id_required")
    return value


def _run_path(run_id: str, runtime_root: Path | None = None) -> Path:
    return _runs_dir(runtime_root) / f"{_validate_run_id(run_id)}.json"


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _outbox_result_path(run_id: str) -> Path:
    return _repo_root() / "interface" / "outbox" / "tasks" / f"{_validate_run_id(run_id)}.result.json"


def _sync_outbox_ingress_projection(record: Dict[str, Any]) -> None:
    outbox_path = _outbox_result_path(str(record.get("run_id") or ""))
    if not outbox_path.exists():
        return
    payload = json.loads(outbox_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    ingress = outputs.get("json", {}).get("ingress") if isinstance(outputs.get("json"), dict) else None
    if not isinstance(ingress, dict):
        return
    ingress["artifacts"] = list(record.get("artifacts") or [])
    ingress["runtime_state"] = record.get("runtime_state")
    ingress["execution_status"] = record.get("execution_status")
    ingress["block_reason"] = record.get("block_reason")
    ingress["approval_state"] = record.get("approval_state")
    payload["outputs"] = outputs
    _write_json_atomic(outbox_path, payload)


def load_run_state(run_id: str, *, runtime_root: Path | None = None) -> Dict[str, Any]:
    path = _run_path(run_id, runtime_root)
    if not path.exists():
        raise QSRuntimeStateError(f"qs_runtime_state_missing:{_validate_run_id(run_id)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise QSRuntimeStateError("qs_runtime_state_invalid:not_object")
    return payload


def _load_qs_job_runner():
    import sys

    candidates = [
        _repo_root() / "repos" / "qs" / "src",
        Path(__file__).resolve().parents[1] / "repos" / "qs" / "src",
    ]
    for repo_src in candidates:
        if repo_src.exists():
            repo_src_str = str(repo_src)
            if repo_src_str not in sys.path:
                sys.path.insert(0, repo_src_str)
    try:
        from universal_qs_engine.job_registry import run_registered_job  # type: ignore[import-not-found]
    except Exception as exc:
        raise QSRuntimeStateError(f"qs_job_registry_unavailable:{exc}") from exc
    return run_registered_job


def _requires_approval(job_type: str) -> bool:
    return str(job_type).strip() == "qs.po_generate"


def _normalize_artifact_record(raw: Any, *, index: int) -> Dict[str, str]:
    if not isinstance(raw, dict):
        raise QSRuntimeStateError(f"qs_runtime_state_invalid:artifact_not_object:{index}")
    artifact_type = str(raw.get("artifact_type") or "").strip()
    path = str(raw.get("path") or "").strip()
    if not artifact_type:
        raise QSRuntimeStateError(f"qs_runtime_state_invalid:artifact_type_required:{index}")
    if not path:
        raise QSRuntimeStateError(f"qs_runtime_state_invalid:artifact_path_required:{index}")
    record = {
        "artifact_type": artifact_type,
        "path": path,
    }
    created_at = raw.get("created_at")
    if created_at is not None:
        created_at_value = str(created_at).strip()
        if not created_at_value:
            raise QSRuntimeStateError(f"qs_runtime_state_invalid:artifact_created_at_blank:{index}")
        record["created_at"] = created_at_value
    return record


def extract_artifact_refs(ingress_payload: Any) -> list[Dict[str, str]]:
    if ingress_payload is None:
        return []
    if not isinstance(ingress_payload, dict):
        raise QSRuntimeStateError("qs_runtime_state_invalid:payload_not_object")
    body = ingress_payload.get("body")
    if body is None:
        return []
    if not isinstance(body, dict):
        raise QSRuntimeStateError("qs_runtime_state_invalid:payload_body_not_object")
    envelope_payload = body.get("envelope_payload")
    if envelope_payload is None:
        return []
    if not isinstance(envelope_payload, dict):
        raise QSRuntimeStateError("qs_runtime_state_invalid:envelope_payload_not_object")
    artifact_refs = envelope_payload.get("artifact_refs")
    if artifact_refs is None:
        return []
    if not isinstance(artifact_refs, list):
        raise QSRuntimeStateError("qs_runtime_state_invalid:artifact_refs_not_list")
    return [_normalize_artifact_record(item, index=index) for index, item in enumerate(artifact_refs)]


def _execute_registered_job_if_allowed(record: Dict[str, Any]) -> Dict[str, Any]:
    if str(record.get("execution_status") or "") != "allowed":
        return record
    run_registered_job = _load_qs_job_runner()
    context = {
        "run_id": str(record.get("run_id") or ""),
        "job_type": str(record.get("job_type") or ""),
        "project_id": str(record.get("project_id") or ""),
    }
    try:
        job_result = run_registered_job(context["job_type"], context)
    except Exception as exc:
        record["job_execution_state"] = "failed"
        record["job_execution_error"] = str(exc)
        record["runtime_state"] = "failed"
        record["execution_status"] = "failed"
        record["block_reason"] = "job_execution_failed"
        record["updated_at"] = _utc_now()
        raise QSRuntimeStateError(f"qs_job_execution_failed:{exc}") from exc

    if not isinstance(job_result, dict):
        record["job_execution_state"] = "failed"
        record["job_execution_error"] = "job_result_not_object"
        record["runtime_state"] = "failed"
        record["execution_status"] = "failed"
        record["block_reason"] = "job_execution_failed"
        record["updated_at"] = _utc_now()
        raise QSRuntimeStateError("qs_job_execution_failed:job_result_not_object")

    raw_refs = job_result.get("artifact_refs")
    if not isinstance(raw_refs, list):
        record["job_execution_state"] = "failed"
        record["job_execution_error"] = "artifact_refs_not_list"
        record["runtime_state"] = "failed"
        record["execution_status"] = "failed"
        record["block_reason"] = "job_execution_failed"
        record["updated_at"] = _utc_now()
        raise QSRuntimeStateError("qs_job_execution_failed:artifact_refs_not_list")

    record["artifacts"] = [_normalize_artifact_record(item, index=index) for index, item in enumerate(raw_refs)]
    record["job_execution_state"] = "completed"
    record["job_execution_error"] = None
    record["updated_at"] = _utc_now()
    return record


def record_ingress_state(
    *,
    run_id: str,
    job_type: str,
    project_id: str,
    qs_status: str,
    ingress_payload: Any = None,
    runtime_root: Path | None = None,
) -> Dict[str, Any]:
    normalized_run_id = _validate_run_id(run_id)
    normalized_job_type = str(job_type or "").strip()
    normalized_project_id = str(project_id or "").strip()
    normalized_status = str(qs_status or "").strip()
    if not normalized_job_type:
        raise QSRuntimeStateError("qs_runtime_state_invalid:job_type_required")
    if not normalized_project_id:
        raise QSRuntimeStateError("qs_runtime_state_invalid:project_id_required")
    if normalized_status not in {"completed", "failed", "rejected"}:
        raise QSRuntimeStateError(f"qs_runtime_state_invalid:status:{normalized_status or 'missing'}")

    requires_approval = _requires_approval(normalized_job_type)
    artifacts = extract_artifact_refs(ingress_payload)
    record = {
        "run_id": normalized_run_id,
        "job_type": normalized_job_type,
        "project_id": normalized_project_id,
        "qs_status": normalized_status,
        "artifacts": artifacts,
        "requires_approval": requires_approval,
        "approval_state": "pending_approval" if requires_approval else "not_required",
        "runtime_state": "pending_approval" if requires_approval else "accepted",
        "execution_status": "blocked" if requires_approval else "allowed",
        "block_reason": "approval_required" if requires_approval else None,
        "approved_by": None,
        "approved_at": None,
        "approval_reason": None,
        "job_execution_state": "not_started",
        "job_execution_error": None,
        "updated_at": _utc_now(),
    }
    if not requires_approval:
        try:
            record = _execute_registered_job_if_allowed(record)
        except QSRuntimeStateError:
            _write_json_atomic(_run_path(normalized_run_id, runtime_root), record)
            _sync_outbox_ingress_projection(record)
            raise
    _write_json_atomic(_run_path(normalized_run_id, runtime_root), record)
    _sync_outbox_ingress_projection(record)
    return record


def approve_run(run_id: str, *, actor: str, reason: str | None = None, runtime_root: Path | None = None) -> Dict[str, Any]:
    actor_value = str(actor or "").strip()
    if not actor_value:
        raise QSRuntimeStateError("qs_runtime_state_invalid:actor_required")
    record = load_run_state(run_id, runtime_root=runtime_root)
    if not bool(record.get("requires_approval")):
        raise QSRuntimeStateError("qs_runtime_state_invalid:approval_not_required")
    if str(record.get("runtime_state", "")).strip() == "rejected_by_operator":
        raise QSRuntimeStateError("qs_runtime_state_invalid:already_rejected")

    record["approval_state"] = "approved"
    record["runtime_state"] = "approved"
    record["execution_status"] = "allowed"
    record["block_reason"] = None
    record["approved_by"] = actor_value
    record["approved_at"] = _utc_now()
    record["approval_reason"] = str(reason).strip() if isinstance(reason, str) and reason.strip() else None
    record["updated_at"] = _utc_now()
    try:
        record = _execute_registered_job_if_allowed(record)
    except QSRuntimeStateError:
        _write_json_atomic(_run_path(run_id, runtime_root), record)
        _sync_outbox_ingress_projection(record)
        raise
    _write_json_atomic(_run_path(run_id, runtime_root), record)
    _sync_outbox_ingress_projection(record)
    return record


def reject_run(run_id: str, *, actor: str, reason: str | None = None, runtime_root: Path | None = None) -> Dict[str, Any]:
    actor_value = str(actor or "").strip()
    if not actor_value:
        raise QSRuntimeStateError("qs_runtime_state_invalid:actor_required")
    record = load_run_state(run_id, runtime_root=runtime_root)
    if not bool(record.get("requires_approval")):
        raise QSRuntimeStateError("qs_runtime_state_invalid:approval_not_required")
    if str(record.get("runtime_state", "")).strip() == "approved":
        raise QSRuntimeStateError("qs_runtime_state_invalid:already_approved")

    record["approval_state"] = "rejected_by_operator"
    record["runtime_state"] = "rejected_by_operator"
    record["execution_status"] = "blocked"
    record["block_reason"] = "operator_rejected"
    record["approved_by"] = actor_value
    record["approved_at"] = _utc_now()
    record["approval_reason"] = str(reason).strip() if isinstance(reason, str) and reason.strip() else None
    record["updated_at"] = _utc_now()
    _write_json_atomic(_run_path(run_id, runtime_root), record)
    return record
