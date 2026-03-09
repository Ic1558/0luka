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

from core.config import COMPLETED, INBOX, REJECTED, ROOT as CONFIG_ROOT, RUNTIME_ROOT
from interface.operator import mission_control_server as mission_control


class RuntimeValidationError(RuntimeError):
    pass


ALLOWED_QS_STATUS = {"completed", "failed", "rejected"}
ALLOWED_APPROVAL_STATE = {"pending_approval", "approved", "rejected_by_operator", "not_required"}
ALLOWED_RUNTIME_STATE = {"accepted", "pending_approval", "approved", "rejected_by_operator", "failed"}
ALLOWED_EXECUTION_STATUS = {"allowed", "blocked", "failed", "pending"}
ALLOWED_JOB_EXECUTION_STATE = {"not_started", "completed", "failed"}


def _qs_runs_dir() -> Path:
    return RUNTIME_ROOT / "state" / "qs_runs"


def _runtime_artifacts_root() -> Path:
    return RUNTIME_ROOT / "artifacts"


def _outbox_result_path(run_id: str) -> Path:
    return CONFIG_ROOT / "interface" / "outbox" / "tasks" / f"{run_id}.result.json"


def _error(category: str, run_id: str | None, detail: str) -> dict[str, Any]:
    return {"category": category, "run_id": run_id, "detail": detail}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeValidationError(f"json_not_object:{path}")
    return payload


def _load_run_records(target_run_id: str | None = None) -> list[dict[str, Any]]:
    runs_dir = _qs_runs_dir()
    if not runs_dir.exists():
        return []
    paths = [runs_dir / f"{target_run_id}.json"] if target_run_id else sorted(runs_dir.glob("*.json"))
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            raise RuntimeValidationError(f"run_not_found:{path.stem}")
        payload = _load_json(path)
        payload["_path"] = str(path)
        records.append(payload)
    return records


def _normalize_artifact_refs(raw: Any, *, run_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    if raw is None:
        return [], errors
    if not isinstance(raw, list):
        return [], [_error("ARTIFACT_ERROR", run_id, "artifact_refs_not_list")]
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            errors.append(_error("ARTIFACT_ERROR", run_id, f"artifact_ref_not_object:{index}"))
            continue
        artifact_type = str(entry.get("artifact_type") or "").strip()
        path = str(entry.get("path") or "").strip()
        created_at = entry.get("created_at")
        if not artifact_type:
            errors.append(_error("ARTIFACT_ERROR", run_id, f"artifact_type_required:{index}"))
        if not path:
            errors.append(_error("ARTIFACT_ERROR", run_id, f"artifact_path_required:{index}"))
        if created_at is not None and not str(created_at).strip():
            errors.append(_error("ARTIFACT_ERROR", run_id, f"artifact_created_at_blank:{index}"))
        normalized.append(entry)
    return normalized, errors


def _validate_run_schema(record: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    run_id = str(record.get("run_id") or "").strip()
    job_type = str(record.get("job_type") or "").strip()
    project_id = str(record.get("project_id") or "").strip()
    qs_status = str(record.get("qs_status") or "").strip()
    approval_state = str(record.get("approval_state") or "").strip()
    runtime_state = str(record.get("runtime_state") or "").strip()
    execution_status = str(record.get("execution_status") or "").strip()
    job_execution_state = str(record.get("job_execution_state") or "").strip()

    if not run_id:
        errors.append(_error("STATE_ERROR", None, "run_id_required"))
    if not job_type:
        errors.append(_error("STATE_ERROR", run_id or None, "job_type_required"))
    if not project_id:
        errors.append(_error("STATE_ERROR", run_id or None, "project_id_required"))
    if qs_status not in ALLOWED_QS_STATUS:
        errors.append(_error("STATE_ERROR", run_id or None, f"invalid_qs_status:{qs_status or 'missing'}"))
    if approval_state not in ALLOWED_APPROVAL_STATE:
        errors.append(_error("STATE_ERROR", run_id or None, f"invalid_approval_state:{approval_state or 'missing'}"))
    if runtime_state not in ALLOWED_RUNTIME_STATE:
        errors.append(_error("STATE_ERROR", run_id or None, f"invalid_runtime_state:{runtime_state or 'missing'}"))
    if execution_status not in ALLOWED_EXECUTION_STATUS:
        errors.append(_error("STATE_ERROR", run_id or None, f"invalid_execution_status:{execution_status or 'missing'}"))
    if job_execution_state not in ALLOWED_JOB_EXECUTION_STATE:
        errors.append(_error("STATE_ERROR", run_id or None, f"invalid_job_execution_state:{job_execution_state or 'missing'}"))
    return errors


def _validate_approval_rules(record: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    run_id = str(record.get("run_id") or "").strip() or None
    requires_approval = bool(record.get("requires_approval"))
    approval_state = str(record.get("approval_state") or "").strip()
    execution_status = str(record.get("execution_status") or "").strip()
    job_execution_state = str(record.get("job_execution_state") or "").strip()
    runtime_state = str(record.get("runtime_state") or "").strip()

    if requires_approval:
        if approval_state == "pending_approval" and execution_status != "blocked":
            errors.append(_error("APPROVAL_ERROR", run_id, "pending_approval_must_be_blocked"))
        if approval_state == "pending_approval" and job_execution_state != "not_started":
            errors.append(_error("APPROVAL_ERROR", run_id, "job_started_before_approval"))
        if approval_state == "approved" and execution_status == "blocked":
            errors.append(_error("APPROVAL_ERROR", run_id, "approved_run_still_blocked"))
        if approval_state == "rejected_by_operator" and runtime_state != "rejected_by_operator":
            errors.append(_error("APPROVAL_ERROR", run_id, "rejected_run_state_mismatch"))
    else:
        if approval_state != "not_required":
            errors.append(_error("APPROVAL_ERROR", run_id, "approval_state_must_be_not_required"))
    return errors


def _validate_projection_consistency(record: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    run_id = str(record.get("run_id") or "").strip() or None
    if not run_id:
        return errors
    try:
        projection = mission_control.load_qs_run(run_id)["run"]
    except Exception as exc:
        return [_error("PROJECTION_DRIFT", run_id, f"projection_unavailable:{exc}")]

    keys = (
        "run_id",
        "job_type",
        "project_id",
        "qs_status",
        "requires_approval",
        "approval_state",
        "runtime_state",
        "execution_status",
        "block_reason",
        "approved_by",
        "approved_at",
        "approval_reason",
        "artifacts",
    )
    for key in keys:
        if projection.get(key) != record.get(key):
            errors.append(_error("PROJECTION_DRIFT", run_id, f"field_mismatch:{key}"))

    outbox_path = _outbox_result_path(run_id)
    if outbox_path.exists():
        try:
            outbox_payload = _load_json(outbox_path)
            outputs = outbox_payload.get("outputs")
            json_payload = outputs.get("json") if isinstance(outputs, dict) else None
            ingress = json_payload.get("ingress") if isinstance(json_payload, dict) else None
            if isinstance(ingress, dict):
                for key in ("run_id", "job_type", "project_id", "status", "runtime_state", "execution_status", "approval_state", "artifacts"):
                    expected = record.get("qs_status") if key == "status" else record.get(key)
                    if ingress.get(key) != expected:
                        errors.append(_error("PROJECTION_DRIFT", run_id, f"outbox_mismatch:{key}"))
        except Exception as exc:
            errors.append(_error("PROJECTION_DRIFT", run_id, f"outbox_unreadable:{exc}"))
    return errors


def _validate_artifacts(record: dict[str, Any], *, strict_existence: bool) -> list[dict[str, Any]]:
    run_id = str(record.get("run_id") or "").strip() or None
    refs, errors = _normalize_artifact_refs(record.get("artifacts"), run_id=run_id or "unknown")
    job_execution_state = str(record.get("job_execution_state") or "").strip()
    execution_status = str(record.get("execution_status") or "").strip()
    qs_status = str(record.get("qs_status") or "").strip()

    if refs and (job_execution_state == "failed" or execution_status == "failed" or qs_status != "completed"):
        errors.append(_error("ARTIFACT_ERROR", run_id, "artifacts_present_on_non_success_run"))

    if strict_existence:
        artifacts_root = _runtime_artifacts_root().resolve()
        for index, ref in enumerate(refs):
            rel_path = str(ref.get("path") or "").strip()
            if not rel_path:
                continue
            resolved = (CONFIG_ROOT / rel_path).resolve() if not Path(rel_path).is_absolute() else Path(rel_path).resolve()
            if artifacts_root not in resolved.parents and resolved != artifacts_root:
                errors.append(_error("ARTIFACT_ERROR", run_id, f"artifact_outside_runtime_root:{index}"))
                continue
            if not resolved.exists():
                errors.append(_error("ARTIFACT_ERROR", run_id, f"artifact_missing:{index}"))
    return errors


def _validate_queue_integrity() -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    locations = {
        "inbox": INBOX,
        "completed": COMPLETED,
        "rejected": REJECTED,
    }
    presence: dict[str, list[str]] = {}
    for label, base in locations.items():
        if not base.exists():
            continue
        for path in base.glob("*.yaml"):
            presence.setdefault(path.name, []).append(label)
    for name, labels in sorted(presence.items()):
        if len(labels) > 1:
            errors.append(_error("QUEUE_ERROR", Path(name).stem, f"task_present_in_multiple_queues:{','.join(labels)}"))
    return errors


def _summarize(report: dict[str, Any]) -> dict[str, int]:
    categories = ("STATE_ERROR", "TRANSITION_ERROR", "APPROVAL_ERROR", "ARTIFACT_ERROR", "PROJECTION_DRIFT", "QUEUE_ERROR")
    return {key.lower(): sum(1 for row in report["errors"] if row["category"] == key) for key in categories}


def validate_runtime(*, mode: str, run_id: str | None = None, strict_artifacts: bool = False) -> dict[str, Any]:
    records = _load_run_records(target_run_id=run_id)
    errors: list[dict[str, Any]] = []
    errors.extend(_validate_queue_integrity())

    for record in records:
        errors.extend(_validate_run_schema(record))
        if mode in {"full", "run"}:
            errors.extend(_validate_approval_rules(record))
            errors.extend(_validate_artifacts(record, strict_existence=strict_artifacts))
            errors.extend(_validate_projection_consistency(record))

    summary = _summarize({"errors": errors})
    report = {
        "mode": mode,
        "run_id": run_id,
        "runs_scanned": len(records),
        "errors": errors,
        "runtime_status": "healthy" if not errors else "invalid",
    }
    report.update(summary)
    return report


def _runtime_root_env() -> Path:
    # core.config already enforces LUKA_RUNTIME_ROOT, but keep this helper
    # for tests that may patch env/paths.
    return Path(os.environ.get("LUKA_RUNTIME_ROOT", str(RUNTIME_ROOT))).expanduser().resolve()


def _activity_feed_path() -> Path:
    return _runtime_root_env() / "logs" / "activity_feed.jsonl"


def _verification_artifact_path(trace_id: str) -> Path:
    return _runtime_root_env() / "artifacts" / "tasks" / trace_id / "verification.json"


def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    tmp.write_text(data + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _find_outbox_result_by_trace_id(trace_id: str) -> tuple[dict[str, Any] | None, str | None]:
    outbox_dir = CONFIG_ROOT / "interface" / "outbox" / "tasks"
    if not outbox_dir.exists():
        return None, None
    for path in sorted(outbox_dir.glob("*.result.json")):
        try:
            payload = _load_json(path)
        except Exception:
            continue
        prov = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else None
        if prov and str(prov.get("trace_id") or "") == trace_id:
            return payload, str(path)
    return None, None


def _find_provenance_ref(trace_id: str) -> str | None:
    prov_path = CONFIG_ROOT / "observability" / "artifacts" / "run_provenance.jsonl"
    for row in _iter_jsonl(prov_path):
        if str(row.get("trace_id") or "") == trace_id:
            # return a truthful pointer, not the row itself
            return str(prov_path)
    return None


def _find_activity_feed_matches(trace_id: str) -> tuple[int, dict[str, Any] | None]:
    # Preferred match is explicit trace_id, but allow task_id == trace_id
    # because many feeds use task_id as the only correlation key.
    matches = 0
    chain_ref: dict[str, Any] | None = None
    for row in _iter_jsonl(_activity_feed_path()):
        if str(row.get("trace_id") or "") == trace_id or str(row.get("task_id") or "") == trace_id:
            matches += 1
            if chain_ref is None:
                maybe_hash = row.get("hash")
                maybe_prev = row.get("prev_hash")
                if isinstance(maybe_hash, str) and maybe_hash and isinstance(maybe_prev, str) and maybe_prev:
                    chain_ref = {"hash": maybe_hash, "prev_hash": maybe_prev}
    return matches, chain_ref


def run_verification_chain(trace_id: str) -> dict[str, Any]:
    """
    Produce a bounded verification chain for a trace_id using existing truth surfaces:
    - outbound/result gate (if available)
    - run_provenance.jsonl existence
    - activity_feed.jsonl presence
    Writes an atomic verification artifact under runtime_root/artifacts/tasks/<trace_id>/verification.json.
    """
    trace_id = str(trace_id or "").strip()
    gates: dict[str, Any] = {
        "outbound_result_gate": "unavailable",
        "provenance_exists": False,
        "activity_feed_present": False,
    }
    evidence: dict[str, Any] = {"feed_match_count": 0}

    if not trace_id:
        result = {"trace_id": "", "gates": gates, "verdict": "failed", "evidence": evidence}
        _write_atomic_json(_verification_artifact_path("unknown_trace"), result)
        return result

    # 1) Outbound/result gate (fail-closed)
    outbox_result, outbox_path = _find_outbox_result_by_trace_id(trace_id)
    if outbox_result is None:
        gates["outbound_result_gate"] = "failed"
    else:
        try:
            from core.phase1d_result_gate import gate_outbound_result  # type: ignore

            gate_outbound_result(outbox_result)
            gates["outbound_result_gate"] = "passed"
            evidence["outbox_result_ref"] = outbox_path
        except Exception as exc:
            # Truthful failure: gate rejected or gate unavailable at runtime.
            gates["outbound_result_gate"] = "failed"
            evidence["outbound_gate_error"] = str(exc)[:240]

    # 2) Run provenance existence
    prov_ref = _find_provenance_ref(trace_id)
    if prov_ref:
        gates["provenance_exists"] = True
        evidence["provenance_ref"] = prov_ref

    # 3) Activity feed presence
    feed_count, chain_ref = _find_activity_feed_matches(trace_id)
    evidence["feed_match_count"] = feed_count
    if feed_count > 0:
        gates["activity_feed_present"] = True
    if chain_ref:
        evidence["hash_chain_ref"] = chain_ref

    verified = (
        gates["outbound_result_gate"] == "passed"
        and gates["provenance_exists"] is True
        and gates["activity_feed_present"] is True
    )
    result = {
        "trace_id": trace_id,
        "gates": gates,
        "verdict": "verified" if verified else "failed",
        "evidence": evidence,
    }
    _write_atomic_json(_verification_artifact_path(trace_id), result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate 0luka runtime state against current invariants.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="Check runtime state schema and queue integrity.")
    group.add_argument("--full", action="store_true", help="Check runtime state, approvals, artifacts, and projections.")
    group.add_argument("--run", metavar="RUN_ID", help="Validate a single run_id with full checks.")
    parser.add_argument("--artifacts", action="store_true", help="Require artifact files to exist under runtime_root/artifacts.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.run:
        mode = "run"
    elif args.quick:
        mode = "quick"
    else:
        mode = "full"

    report = validate_runtime(mode=mode, run_id=args.run, strict_artifacts=args.artifacts)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print("0LUKA Runtime Validation Report")
        print(f"Runs scanned: {report['runs_scanned']}")
        print(f"State errors: {report['state_error']}")
        print(f"Transition errors: {report['transition_error']}")
        print(f"Approval errors: {report['approval_error']}")
        print(f"Artifact errors: {report['artifact_error']}")
        print(f"Projection drift: {report['projection_drift']}")
        print(f"Queue errors: {report['queue_error']}")
        print(f"Runtime status: {str(report['runtime_status']).upper()}")
    return 0 if report["runtime_status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
