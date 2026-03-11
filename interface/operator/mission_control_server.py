#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from string import Template
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    # This module's endpoints expect raw Starlette request objects rather than
    # FastAPI parameter parsing, so use the Starlette route path consistently.
    FASTAPI_AVAILABLE = False
except ImportError:  # pragma: no cover
    from starlette.applications import Starlette as FastAPI
    from starlette.responses import HTMLResponse, JSONResponse
    FASTAPI_AVAILABLE = False

from starlette.routing import Route

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import approval_presets, approval_write, remediation_queue
from tools.ops.control_plane_persistence import (
    DecisionPersistenceError,
    append_decision_event,
    append_suggestion_feedback,
    read_decision_history,
    read_latest_decision,
    read_suggestion_feedback,
    record_operator_decision,
)
from tools.ops.control_plane_execution_bridge import (
    ExecutionBridgeError,
    RETRYABLE_OUTCOMES,
    auto_retry_approved_decision,
    escalate_approved_decision,
    handoff_approved_decision,
    retry_approved_decision,
)
from tools.ops.control_plane_suggestions import load_latest_suggestion
from tools.ops.control_plane_policy import load_latest_policy
from tools.ops.control_plane_auto_lane_review import derive_auto_lane_review
from tools.ops.control_plane_auto_lane_queue import load_auto_lane_candidate_queue
from tools.ops.control_plane_auto_lane_trends import load_auto_lane_readiness
from tools.ops.control_plane_policy_change_proposals import (
    PolicyProposalError,
    append_policy_deployment_event,
    approve_policy_change_proposal,
    create_policy_change_proposal,
    get_policy_change_proposal,
    list_policy_change_proposals,
    reject_policy_change_proposal,
)
from tools.ops.control_plane_policy_learning_review import load_policy_learning_review
from tools.ops.control_plane_policy_observability import load_policy_stats
from tools.ops.control_plane_policy_tuning_simulator import load_policy_tuning_preview
from tools.ops.control_plane_policy_preflight import load_policy_preflight
from tools.ops.control_plane_policy_versions import (
    deploy_policy_version,
    get_policy_version,
    list_policy_versions,
    read_live_policy,
    rollback_policy_version,
)
from tools.ops.execution_outcome_reconciler import reconcile_execution_outcome
from tools.ops.decision_engine import classify_once
from tools.ops.run_interpreter import interpret_run

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
CANONICAL_OBSERVABILITY_ROOT = Path("/Users/icmini/0luka/observability")
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7010
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "mission_control.html"


def _observability_root() -> Path:
    raw = os.environ.get("LUKA_OBSERVABILITY_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_OBSERVABILITY_ROOT


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _activity_feed_path() -> Path:
    return _observability_root() / "logs" / "activity_feed.jsonl"


def _alerts_path() -> Path:
    return _runtime_root() / "state" / "alerts.jsonl"


def _approval_actions_path() -> Path:
    return _runtime_root() / "state" / "approval_actions.jsonl"


def _approval_log_path() -> Path:
    primary = _runtime_root() / "state" / "approval_log.jsonl"
    if primary.exists():
        return primary
    return _approval_actions_path()


def _remediation_history_log_path() -> Path:
    return _runtime_root() / "state" / "remediation_history.jsonl"


def _qs_runs_dir() -> Path:
    return _runtime_root() / "state" / "qs_runs"


def _system_model_path() -> Path:
    return _runtime_root() / "state" / "system_model.json"


def _resolve_qs_run_path(run_id: str) -> Path:
    raw = run_id.strip()
    if not raw or raw in {".", ".."} or "/" in raw or "\\" in raw:
        raise ValueError("unsafe_run_id")

    base_dir = _qs_runs_dir().resolve()
    candidate = (_qs_runs_dir() / f"{raw}.json").resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError("unsafe_run_id") from exc
    return candidate


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{path}")
    return payload


def _run_json_command(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    stream = proc.stdout.strip() or proc.stderr.strip()
    if not stream:
        raise RuntimeError(f"empty_output:{' '.join(args)}")
    payload = json.loads(stream)
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{' '.join(args)}")
    return payload


def load_operator_status() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/operator_status_report.py", "--json"])


def load_runtime_status() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/runtime_status_report.py", "--json"])


def load_activity_entries(limit: int = 50) -> list[dict[str, Any]]:
    path = _activity_feed_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def _collect_artifact_directories(
    base_dir: Path,
    *,
    artifact_type: str,
    limit: int,
    manifest_name: str | None = None,
) -> list[dict[str, Any]]:
    if not base_dir.exists() or not base_dir.is_dir():
        return []

    dirs = [path for path in base_dir.iterdir() if path.is_dir()]
    dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)

    rows: list[dict[str, Any]] = []
    for path in dirs[:limit]:
        row: dict[str, Any] = {
            "artifact_type": artifact_type,
            "name": path.name,
            "path": str(path),
            "mtime_utc": path.stat().st_mtime,
        }
        if manifest_name:
            manifest_path = path / manifest_name
            row["manifest_present"] = manifest_path.exists()
        rows.append(row)
    return rows


def load_proof_artifacts(limit: int = 50) -> dict[str, Any]:
    capped_limit = max(1, min(limit, 200))
    entries = [
        *_collect_artifact_directories(
            _observability_root() / "artifacts" / "proof_packs",
            artifact_type="proof_pack",
            limit=capped_limit,
            manifest_name="linter.json",
        ),
        *_collect_artifact_directories(
            _runtime_root() / "exports",
            artifact_type="ledger_proof_export",
            limit=capped_limit,
            manifest_name="export_manifest.json",
        ),
    ]
    entries.sort(key=lambda item: float(item.get("mtime_utc", 0)), reverse=True)
    entries = entries[:capped_limit]
    return {
        "artifacts": entries,
        "total_entries": len(entries),
    }


def _proof_artifact_roots() -> dict[str, Path]:
    return {
        "proof_pack": _observability_root() / "artifacts" / "proof_packs",
        "ledger_proof_export": _runtime_root() / "exports",
    }


def _resolve_proof_artifact_path(artifact_id: str) -> tuple[str, Path] | None:
    raw = artifact_id.strip()
    if ":" not in raw:
        raise ValueError("invalid_artifact_id")
    artifact_type, name = raw.split(":", 1)
    artifact_type = artifact_type.strip()
    name = name.strip()
    if not artifact_type or not name:
        raise ValueError("invalid_artifact_id")
    if name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("unsafe_artifact_id")

    roots = _proof_artifact_roots()
    base_dir = roots.get(artifact_type)
    if base_dir is None:
        raise ValueError("invalid_artifact_type")

    base_resolved = base_dir.resolve()
    candidate = (base_dir / name).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError("unsafe_artifact_id") from exc
    return artifact_type, candidate


def load_proof_artifact_detail(artifact_id: str, *, entry_limit: int = 200) -> dict[str, Any] | None:
    artifact_type, artifact_path = _resolve_proof_artifact_path(artifact_id)
    if not artifact_path.exists() or not artifact_path.is_dir():
        return None

    entries: list[dict[str, Any]] = []
    for entry in sorted(artifact_path.iterdir(), key=lambda item: item.name)[:entry_limit]:
        info: dict[str, Any] = {
            "name": entry.name,
            "is_dir": entry.is_dir(),
            "kind": "dir" if entry.is_dir() else "file",
            "size": None,
        }
        if entry.is_file():
            info["size"] = entry.stat().st_size
        entries.append(info)

    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "root_type": artifact_type,
        "exists": True,
        "path": str(artifact_path),
        "entries": entries,
        "entry_count": len(entries),
    }


def _proof_artifacts_for_run(run_id: str) -> list[str]:
    run_name = run_id.strip()
    if not run_name:
        return []

    artifact_ids: list[str] = []
    for artifact_type in ("proof_pack", "ledger_proof_export"):
        artifact_id = f"{artifact_type}:{run_name}"
        try:
            _, artifact_path = _resolve_proof_artifact_path(artifact_id)
        except ValueError:
            continue
        if artifact_path.exists() and artifact_path.is_dir():
            artifact_ids.append(artifact_id)
    return artifact_ids


def _attach_qs_run_artifacts(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not isinstance(run_id, str):
        result = dict(payload)
        result["proof_artifacts"] = []
        return result

    result = dict(payload)
    result["proof_artifacts"] = _proof_artifacts_for_run(run_id)
    return result


def _attach_qs_run_interpretation(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    proof_artifacts = result.get("proof_artifacts")
    decision = interpret_run(result, proof_artifacts)
    if decision is None:
        result.setdefault("artifact_count", 0)
        result.setdefault("expected_artifacts", [])
        result.setdefault("missing_artifacts", [])
        result.setdefault("signal", None)
        return result

    result["artifact_count"] = decision["artifact_count"]
    result["expected_artifacts"] = decision["expected_artifacts"]
    result["missing_artifacts"] = decision["missing_artifacts"]
    result["signal"] = decision["signal"]
    return result


def load_qs_run_artifacts(run_id: str) -> dict[str, Any] | None:
    run_payload = load_qs_run(run_id)
    if run_payload is None:
        return None

    artifacts: list[dict[str, Any]] = []
    for artifact_type in ("proof_pack", "ledger_proof_export"):
        artifact_id = f"{artifact_type}:{run_id}"
        try:
            _, artifact_path = _resolve_proof_artifact_path(artifact_id)
        except ValueError:
            return None
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "exists": artifact_path.exists() and artifact_path.is_dir(),
            }
        )

    return {
        "run_id": run_id,
        "artifacts": artifacts,
    }


def load_alerts(limit: int = 100) -> list[dict[str, Any]]:
    path = _alerts_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def load_approval_history(lane: str | None = None, last: int | None = None) -> dict[str, Any]:
    path = _approval_actions_path()
    rows: list[dict[str, Any]] = []
    if path.exists():
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
            lane_name = str(row.get("lane") or "")
            if lane and lane_name != lane:
                continue
            rows.append(
                {
                    "timestamp": row.get("timestamp"),
                    "lane": lane_name or None,
                    "action": row.get("action"),
                    "actor": row.get("actor"),
                    "approved": bool(row.get("approved", False)),
                    "expires_at": row.get("expires_at"),
                    "source": row.get("source", "approval_write"),
                }
            )
    if last is not None and last >= 0:
        rows = rows[-last:]
    return {
        "events": rows,
        "last_event": rows[-1] if rows else None,
        "total_entries": len(rows),
    }


def _read_jsonl_entries(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def load_remediation_audit_entries(last: int = 100) -> dict[str, Any]:
    rows = _read_jsonl_entries(_remediation_history_log_path())
    if last >= 0:
        rows = rows[-last:]
    return {"ok": True, "entries": rows}


def load_approval_log_entries(last: int = 100) -> dict[str, Any]:
    rows = _read_jsonl_entries(_approval_log_path())
    if last >= 0:
        rows = rows[-last:]
    return {"ok": True, "entries": rows}


def load_qs_runs(limit: int = 100) -> dict[str, Any]:
    base_dir = _qs_runs_dir()
    if not base_dir.exists() or not base_dir.is_dir():
        return {"ok": True, "runs": [], "total_entries": 0}

    files = [f for f in base_dir.glob("*.json") if f.is_file()]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    runs = []
    for f in files[:limit]:
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                runs.append(_attach_qs_run_interpretation(_attach_qs_run_artifacts(payload)))
        except (json.JSONDecodeError, OSError):
            continue

    return {"ok": True, "runs": runs, "total_entries": len(runs)}


def load_qs_run(run_id: str) -> dict[str, Any] | None:
    try:
        path = _resolve_qs_run_path(run_id)
    except ValueError:
        return None
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return _attach_qs_run_interpretation(_attach_qs_run_artifacts(payload))
    except (json.JSONDecodeError, OSError):
        pass
    return None


def load_system_model() -> dict[str, Any]:
    return _read_json(_system_model_path())


def load_runtime_decisions(last: int = 100) -> dict[str, Any]:
    rows = []
    for entry in _read_jsonl_entries(_remediation_history_log_path()):
        if "decision" not in entry:
            continue
        rows.append(entry)
    if last >= 0:
        rows = rows[-last:]
    return {"ok": True, "entries": rows}


def _build_remediation_timeline(report: dict[str, Any], *, last: int | None = None) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for lane_name in ("memory", "worker"):
        lane_payload = report.get(lane_name)
        if not isinstance(lane_payload, dict):
            continue
        for decision in lane_payload.get("lifecycle", []):
            timeline.append(
                {
                    "timestamp": None,
                    "decision": str(decision),
                    "lane": lane_name,
                }
            )
    if last is not None and last >= 0:
        timeline = timeline[-last:]
    return timeline


def load_remediation_history(lane: str | None = None, last: int | None = None) -> dict[str, Any]:
    args = [sys.executable, "tools/ops/remediation_history_report.py", "--json"]
    if lane:
        args.extend(["--lane", lane])
    if last is not None:
        args.extend(["--last", str(last)])
    payload = _run_json_command(args)
    payload["timeline"] = _build_remediation_timeline(payload, last=last)
    payload.setdefault("last_event", {"decision": None, "lane": None, "timestamp": None})
    payload.setdefault("total_entries", 0)
    for lane_name in ("memory", "worker"):
        if lane and lane_name != lane:
            continue
        if lane_name not in payload:
            payload[lane_name] = {
                "attempts": 0,
                "cooldowns": 0,
                "escalations": 0,
                "recovered": 0,
                "lifecycle": [],
            }
    return payload


def load_autonomy_policy(lane: str | None = None) -> dict[str, Any]:
    args = [sys.executable, "tools/ops/autonomy_policy.py", "--json"]
    if lane:
        args.extend(["--lane", lane])
    return _run_json_command(args)


def apply_approval_action(
    *,
    lane: str,
    actor: str,
    approve: bool = False,
    revoke: bool = False,
    expires_at: str | None = None,
    clear_expiry: bool = False,
) -> dict[str, Any]:
    return approval_write.write_approval_action(
        lane=lane,
        actor=actor,
        approve=approve,
        revoke=revoke,
        expires_at=expires_at,
        clear_expiry=clear_expiry,
    )

def load_approval_presets() -> dict[str, Any]:
    return approval_presets.list_presets(runtime_root=_runtime_root())


def load_approval_expiry() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/approval_expiry_monitor.py", "--json"])


def load_policy_drift() -> dict[str, Any]:
    return _run_json_command([sys.executable, "tools/ops/policy_drift_detector.py", "--json"])


def load_decision_preview() -> dict[str, Any]:
    operator_status: dict[str, Any] | None
    runtime_status: dict[str, Any] | None
    policy_drift: dict[str, Any] | None

    try:
        raw_operator_status = load_operator_status()
        operator_status = raw_operator_status if isinstance(raw_operator_status, dict) else None
    except Exception:
        operator_status = None

    try:
        raw_runtime_status = load_runtime_status()
        runtime_status = raw_runtime_status if isinstance(raw_runtime_status, dict) else None
    except Exception:
        runtime_status = None

    try:
        raw_policy_drift = load_policy_drift()
        policy_drift = raw_policy_drift if isinstance(raw_policy_drift, dict) else None
    except Exception:
        policy_drift = None

    classification: str | None = None
    if operator_status is not None and runtime_status is not None and policy_drift is not None:
        decision = classify_once(
            operator_status=operator_status,
            runtime_status=runtime_status,
            policy_drift=policy_drift,
            ts_utc="decision_preview",
        )
        if isinstance(decision, dict):
            decision_type = decision.get("type")
            classification = decision_type if isinstance(decision_type, str) else None

    return {
        "classification": classification,
        "inputs": {
            "operator_status": operator_status,
            "runtime_status": runtime_status,
            "policy_drift": policy_drift,
        },
    }


def _sanitize_evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    refs: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        text = item.strip()
        if text.startswith("/"):
            text = Path(text).name
        refs.append(text)
    return refs


def _sanitize_decision_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": payload.get("decision_id"),
        "trace_id": payload.get("trace_id"),
        "signal_received": payload.get("signal_received"),
        "proposed_action": payload.get("proposed_action"),
        "evidence_refs": _sanitize_evidence_refs(payload.get("evidence_refs")),
        "ts_utc": payload.get("ts_utc"),
        "operator_status": payload.get("operator_status"),
        "operator_note": payload.get("operator_note"),
    }


def _decorate_decision_with_execution(payload: dict[str, Any]) -> dict[str, Any]:
    decision = _sanitize_decision_payload(payload)
    execution = reconcile_execution_outcome(
        payload,
        repo_root=ROOT,
        observability_root=_observability_root(),
    )
    metadata = _latest_auto_retry_metadata(str(payload.get("decision_id") or ""))
    if isinstance(execution, dict) and isinstance(metadata, dict):
        execution = {
            **execution,
            "policy_execution_status": "AUTO RETRY TRIGGERED",
            "policy_executed": True,
            "policy_reason": metadata.get("policy_reason"),
            "policy_alignment_count": metadata.get("alignment_count"),
        }
    decision["execution"] = execution
    return decision


def load_latest_pending_decision() -> dict[str, Any]:
    try:
        payload = read_latest_decision(_runtime_root())
    except DecisionPersistenceError:
        return {"pending": None, "latest": None}

    if not isinstance(payload, dict):
        return {"pending": None, "latest": None}
    try:
        _maybe_trigger_policy_auto_retry(payload)
    except (DecisionPersistenceError, ExecutionBridgeError):
        pass
    latest = _decorate_decision_with_execution(payload)
    if payload.get("operator_status") != "PENDING":
        return {"pending": None, "latest": latest}
    return {"pending": latest, "latest": latest}


def _history_event_type(value: str) -> str:
    mapping = {
        "PROPOSAL_CREATED": "PROPOSED",
        "OPERATOR_APPROVED": "OPERATOR_APPROVED",
        "OPERATOR_REJECTED": "OPERATOR_REJECTED",
        "PROPOSAL_SUPERSEDED": "PROPOSAL_SUPERSEDED",
        "EXECUTION_HANDOFF_ACCEPTED": "EXECUTION_HANDOFF_ACCEPTED",
        "EXECUTION_RETRY_REQUESTED": "EXECUTION_RETRY_REQUESTED",
        "EXECUTION_ESCALATION_REQUESTED": "EXECUTION_ESCALATION_REQUESTED",
        "AUTO_RETRY_TRIGGERED": "AUTO_RETRY_TRIGGERED",
    }
    return mapping.get(value, "UNKNOWN")


def load_decision_history(limit: int = 50) -> dict[str, Any]:
    try:
        rows = read_decision_history(_observability_root(), limit=limit)
    except DecisionPersistenceError:
        return {"items": [], "count": 0}

    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "decision_id": row.get("decision_id"),
                "trace_id": row.get("trace_id"),
                "event_type": _history_event_type(str(row.get("event") or "")),
                "timestamp": row.get("ts_utc"),
                "operator_status": row.get("operator_status"),
                "proposed_action": row.get("proposed_action"),
                "operator_note": row.get("operator_note"),
                "evidence_refs": _sanitize_evidence_refs(row.get("evidence_refs")),
            }
        )
    return {"items": items, "count": len(items)}


def load_decision_suggestion() -> dict[str, Any]:
    return load_latest_suggestion(
        runtime_root=_runtime_root(),
        observability_root=_observability_root(),
        repo_root=ROOT,
    )


def load_decision_suggestion_feedback(limit: int = 20) -> dict[str, Any]:
    try:
        latest = read_latest_decision(_runtime_root())
    except DecisionPersistenceError:
        latest = None
    decision_id = latest.get("decision_id") if isinstance(latest, dict) else None
    try:
        rows = read_suggestion_feedback(_observability_root(), decision_id=decision_id, limit=limit)
    except DecisionPersistenceError:
        return {"items": [], "count": 0}
    items = [
        {
            "decision_id": row.get("decision_id"),
            "trace_id": row.get("trace_id"),
            "event": row.get("event"),
            "timestamp": row.get("ts_utc"),
            "suggestion": row.get("suggestion"),
            "confidence_band": row.get("confidence_band"),
            "operator_action": row.get("operator_action"),
            "alignment": row.get("alignment"),
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}


def load_decision_policy() -> dict[str, Any]:
    return load_latest_policy(
        runtime_root=_runtime_root(),
        observability_root=_observability_root(),
        repo_root=ROOT,
    )


def load_auto_lane_review_payload() -> dict[str, Any]:
    latest_payload = load_latest_pending_decision()
    latest = latest_payload.get("latest") if isinstance(latest_payload, dict) else None
    return derive_auto_lane_review(latest if isinstance(latest, dict) else None, load_decision_policy())


def load_auto_lane_candidates_payload(*, limit: int = 10) -> dict[str, Any]:
    return load_auto_lane_candidate_queue(
        observability_root=_observability_root(),
        repo_root=ROOT,
        item_limit=limit,
    )


def load_auto_lane_readiness_payload(*, recent_cases: int = 20) -> dict[str, Any]:
    return load_auto_lane_readiness(
        observability_root=_observability_root(),
        repo_root=ROOT,
        recent_cases=recent_cases,
    )


def load_policy_stats_payload() -> dict[str, Any]:
    return load_policy_stats(
        observability_root=_observability_root(),
        repo_root=ROOT,
    )


def load_policy_review_payload() -> dict[str, Any]:
    return load_policy_learning_review(
        observability_root=_observability_root(),
        repo_root=ROOT,
    )


def load_policy_tuning_preview_payload(
    *,
    alignment_threshold: int | str = 2,
    confidence_requirement: str | None = "HIGH",
    recent_cases: int = 20,
) -> dict[str, Any]:
    return load_policy_tuning_preview(
        observability_root=_observability_root(),
        repo_root=ROOT,
        alignment_threshold=alignment_threshold,
        confidence_requirement=confidence_requirement,
        recent_cases=recent_cases,
    )


def load_policy_change_proposals_payload(*, limit: int = 50) -> dict[str, Any]:
    try:
        items = list_policy_change_proposals(_observability_root(), limit=limit)
    except PolicyProposalError:
        items = []
    return {"items": items, "count": len(items)}


def load_policy_change_proposal_detail_payload(proposal_id: str) -> dict[str, Any] | None:
    try:
        return get_policy_change_proposal(_observability_root(), proposal_id)
    except PolicyProposalError:
        return None


def load_policy_version_payload() -> dict[str, Any]:
    try:
        return read_live_policy(_runtime_root())
    except PolicyProposalError:
        return {
            "policy_component": "auto_retry_threshold",
            "current_value": 0.70,
            "policy_version_id": None,
            "deployed_at": None,
            "proposal_id": None,
        }


def load_policy_versions_payload(*, limit: int = 50) -> dict[str, Any]:
    try:
        items = list_policy_versions(_observability_root(), limit=limit)
    except PolicyProposalError:
        items = []
    return {"items": items, "count": len(items)}


def load_policy_preflight_payload(*, component: str, target_value: Any) -> dict[str, Any]:
    return load_policy_preflight(
        runtime_root=_runtime_root(),
        policy_component=component,
        target_value=target_value,
    )


def load_remediation_queue() -> dict[str, Any]:
    return remediation_queue.list_queue(runtime_root=_runtime_root())


def enqueue_remediation_queue(*, lane: str, action: str) -> dict[str, Any]:
    return remediation_queue.enqueue_item(lane=lane, action=action, runtime_root=_runtime_root())


def apply_approval_preset(*, preset: str) -> dict[str, Any]:
    return approval_presets.apply_preset(preset=preset, runtime_root=_runtime_root())


def reset_approval_preset(*, preset: str) -> dict[str, Any]:
    return approval_presets.reset_preset(preset=preset, runtime_root=_runtime_root())


def _epoch_id(runtime_status: dict[str, Any]) -> str:
    proof = runtime_status.get("proof_pack")
    if isinstance(proof, dict):
        epoch = proof.get("epoch_id")
        if epoch is not None:
            return str(epoch)
    return "n/a"


def _activity_html(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "<li>No activity available</li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        ts = escape(str(row.get("ts_utc") or row.get("ts") or "n/a"))
        action = escape(str(row.get("action") or row.get("event") or "unknown"))
        items.append(f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span></li>")
    return "\n".join(items)


def _alerts_html(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "<li class=\"alert-item info\"><span class=\"severity\">INFO</span><span class=\"component\">alerts</span><span class=\"message\">No alerts available</span></li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        severity = escape(str(row.get("severity") or "INFO")).lower()
        ts = escape(str(row.get("timestamp") or "n/a"))
        component = escape(str(row.get("component") or "unknown"))
        message = escape(str(row.get("message") or ""))
        items.append(
            "<li class=\"alert-item {severity}\">"
            "<span class=\"ts\">{ts}</span>"
            "<span class=\"severity\">{sev}</span>"
            "<span class=\"component\">{component}</span>"
            "<span class=\"message\">{message}</span>"
            "</li>".format(
                severity=severity,
                ts=ts,
                sev=escape(str(row.get("severity") or "INFO")),
                component=component,
                message=message,
            )
        )
    return "\n".join(items)


def _remediation_summary_html(report: dict[str, Any]) -> str:
    blocks: list[str] = []
    for lane_name in ("memory", "worker"):
        lane_payload = report.get(lane_name)
        if not isinstance(lane_payload, dict):
            continue
        blocks.append(
            "<div class=\"lane-block\">"
            f"<h3>{escape(lane_name.title())}</h3>"
            "<dl>"
            f"<dt>Attempts</dt><dd>{escape(str(lane_payload.get('attempts', 0)))}</dd>"
            f"<dt>Cooldowns</dt><dd>{escape(str(lane_payload.get('cooldowns', 0)))}</dd>"
            f"<dt>Escalations</dt><dd>{escape(str(lane_payload.get('escalations', 0)))}</dd>"
            f"<dt>Recovered</dt><dd>{escape(str(lane_payload.get('recovered', 0)))}</dd>"
            "</dl>"
            "</div>"
        )
    if not blocks:
        return "<p class=\"muted\">No remediation history available</p>"
    return "\n".join(blocks)


def _remediation_last_event_html(report: dict[str, Any]) -> str:
    event = report.get("last_event")
    if not isinstance(event, dict):
        event = {}
    return (
        "<dl>"
        f"<dt>Decision</dt><dd>{escape(str(event.get('decision') or 'n/a'))}</dd>"
        f"<dt>Lane</dt><dd>{escape(str(event.get('lane') or 'n/a'))}</dd>"
        f"<dt>Timestamp</dt><dd>{escape(str(event.get('timestamp') or 'n/a'))}</dd>"
        "</dl>"
    )


def _remediation_timeline_html(report: dict[str, Any]) -> str:
    entries = report.get("timeline")
    if not isinstance(entries, list) or not entries:
        return "<li>No remediation events available</li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        if not isinstance(row, dict):
            continue
        ts = escape(str(row.get("timestamp") or "n/a"))
        decision = escape(str(row.get("decision") or "unknown"))
        lane = escape(str(row.get("lane") or "unknown"))
        items.append(
            f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{decision}</span> <span class=\"lane\">({lane})</span></li>"
        )
    return "\n".join(items) if items else "<li>No remediation events available</li>"


def _approval_history_last_event_html(payload: dict[str, Any]) -> str:
    event = payload.get("last_event")
    if not isinstance(event, dict):
        event = {}
    return (
        "<dl>"
        f"<dt>Action</dt><dd>{escape(str(event.get('action') or 'n/a'))}</dd>"
        f"<dt>Lane</dt><dd>{escape(str(event.get('lane') or 'n/a'))}</dd>"
        f"<dt>Actor</dt><dd>{escape(str(event.get('actor') or 'n/a'))}</dd>"
        f"<dt>Timestamp</dt><dd>{escape(str(event.get('timestamp') or 'n/a'))}</dd>"
        "</dl>"
    )


def _approval_history_timeline_html(payload: dict[str, Any]) -> str:
    entries = payload.get("events")
    if not isinstance(entries, list) or not entries:
        return "<li>No approval history available</li>"
    items: list[str] = []
    for row in reversed(entries[-10:]):
        if not isinstance(row, dict):
            continue
        ts = escape(str(row.get("timestamp") or "n/a"))
        action = escape(str(row.get("action") or "unknown"))
        lane = escape(str(row.get("lane") or "unknown"))
        actor = escape(str(row.get("actor") or "n/a"))
        expires = escape(str(row.get("expires_at") or "n/a"))
        items.append(
            f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span> "
            f"<span class=\"lane\">({lane})</span> <span class=\"actor\">by {actor}</span> "
            f"<span class=\"expiry\">expires={expires}</span></li>"
        )
    return "\n".join(items) if items else "<li>No approval history available</li>"


def _autonomy_policy_html(payload: dict[str, Any]) -> str:
    lanes = payload.get("lanes")
    if not isinstance(lanes, dict) or not lanes:
        return "<li>No autonomy policy available</li>"
    items: list[str] = []
    for lane_name in ("memory_recovery", "worker_recovery", "api_recovery", "redis_recovery"):
        row = lanes.get(lane_name)
        if not isinstance(row, dict):
            continue
        items.append(
            "<li class=\"policy-item status-{status}\">"
            "<span class=\"lane-name\">{lane}</span>"
            "<span class=\"policy-status\">{state}</span>"
            "<span class=\"policy-reason\">{reason}</span>"
            "<span class=\"policy-meta\">approval={approval}; expires={expires}; expired={expired}; expiring_soon={expiring}</span>"
            "<div class=\"policy-controls\">"
            "<input class=\"policy-actor\" data-lane=\"{lane_raw}\" placeholder=\"actor\">"
            "<input class=\"policy-expiry\" data-lane=\"{lane_raw}\" placeholder=\"expires_at (UTC)\">"
            "<button type=\"button\" onclick=\"submitApprovalAction('approve','{lane_raw}')\">Approve</button>"
            "<button type=\"button\" onclick=\"submitApprovalAction('revoke','{lane_raw}')\">Revoke</button>"
            "<button type=\"button\" onclick=\"submitApprovalExpiry('{lane_raw}', false)\">Set Expiry</button>"
            "<button type=\"button\" onclick=\"submitApprovalExpiry('{lane_raw}', true)\">Clear Expiry</button>"
            "</div>"
            "</li>".format(
                lane=escape(lane_name),
                lane_raw=escape(lane_name),
                status=escape(str(row.get("status", "denied")).lower()),
                state=escape(str(row.get("status", "denied"))),
                reason=escape(str(row.get("reason", "unknown"))),
                approval=escape(str(row.get("approval_state", "invalid"))),
                expires=escape(str(row.get("expires_at") or "n/a")),
                expired=escape(str(bool(row.get("expired"))).lower()),
                expiring=escape(str(bool(row.get("expiring_soon"))).lower()),
            )
        )
    return "\n".join(items) if items else "<li>No autonomy policy available</li>"


def _approval_presets_html(payload: dict[str, Any]) -> str:
    presets = payload.get("presets")
    if not isinstance(presets, list) or not presets:
        return "<li>No approval presets available</li>"
    items: list[str] = []
    for row in presets:
        if not isinstance(row, dict):
            continue
        name = escape(str(row.get("name") or "unknown"))
        lanes = row.get("lanes")
        lanes_text = ", ".join(str(x) for x in lanes) if isinstance(lanes, list) and lanes else "none"
        last_applied_at = escape(str(row.get("last_applied_at") or "n/a"))
        items.append(
            "<li class=\"policy-item\">"
            f"<span class=\"lane-name\">{name}</span>"
            f"<span class=\"policy-meta\">lanes={escape(lanes_text)}; last_applied={last_applied_at}</span>"
            "<div class=\"policy-controls\">"
            f"<button type=\"button\" onclick=\"submitPresetAction('apply','{name}')\">Apply</button>"
            f"<button type=\"button\" onclick=\"submitPresetAction('reset','{name}')\">Reset</button>"
            "</div>"
            "</li>"
        )
    return "\n".join(items) if items else "<li>No approval presets available</li>"


def _approval_expiry_html(payload: dict[str, Any]) -> str:
    lanes = payload.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        return "<li>No approval expiry data available</li>"
    rows: list[str] = []
    for row in lanes:
        if not isinstance(row, dict):
            continue
        lane = escape(str(row.get("lane") or "unknown"))
        status = escape(str(row.get("status") or "OK"))
        actor = escape(str(row.get("actor") or "n/a"))
        expires_at = escape(str(row.get("expires_at") or "n/a"))
        rows.append(
            f"<li class=\"policy-item status-{status.lower()}\">"
            f"<span class=\"lane-name\">{lane}</span>"
            f"<span class=\"policy-status\">{status}</span>"
            f"<span class=\"policy-meta\">actor={actor}; expires_at={expires_at}</span>"
            "</li>"
        )
    return "\n".join(rows) if rows else "<li>No approval expiry data available</li>"


def _policy_drift_html(payload: dict[str, Any]) -> str:
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        return "<li>No policy drift data available</li>"
    rows: list[str] = []
    for key in (
        "approval_log_consistency",
        "expiry_consistency",
        "env_gate_consistency",
        "lane_registry_consistency",
    ):
        status = str(checks.get(key, "UNKNOWN"))
        rows.append(
            f"<li class=\"policy-item status-{escape(status.lower())}\">"
            f"<span class=\"lane-name\">{escape(key)}</span>"
            f"<span class=\"policy-status\">{escape(status)}</span>"
            "</li>"
        )
    return "\n".join(rows) if rows else "<li>No policy drift data available</li>"


def _remediation_queue_html(payload: dict[str, Any]) -> str:
    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        return "<li>No remediation queue items</li>"
    items: list[str] = []
    for row in reversed(rows[-10:]):
        if not isinstance(row, dict):
            continue
        items.append(
            "<li class=\"policy-item status-{state}\">"
            "<span class=\"lane-name\">{item_id}</span>"
            "<span class=\"policy-status\">{state}</span>"
            "<span class=\"policy-meta\">lane={lane}; action={action}; attempts={attempts}; created_at={created_at}</span>"
            "</li>".format(
                item_id=escape(str(row.get("id") or "n/a")),
                state=escape(str(row.get("state") or "queued")).lower(),
                lane=escape(str(row.get("lane") or "unknown")),
                action=escape(str(row.get("action") or "unknown")),
                attempts=escape(str(row.get("attempts", 0))),
                created_at=escape(str(row.get("created_at") or "n/a")),
            )
        )
    return "\n".join(items) if items else "<li>No remediation queue items</li>"


def _audit_entries_html(payload: dict[str, Any], *, kind: str) -> str:
    rows = payload.get("entries")
    if not isinstance(rows, list) or not rows:
        return "<li>No entries available</li>"
    items: list[str] = []
    for row in reversed(rows[-10:]):
        if not isinstance(row, dict):
            continue
        ts = escape(str(row.get("timestamp") or "n/a"))
        lane = escape(str(row.get("lane") or "n/a"))
        action = escape(str(row.get("action") or row.get("decision") or "unknown"))
        actor = escape(str(row.get("actor") or "n/a"))
        result = escape(str(row.get("result") or "n/a"))
        if kind == "runtime_decisions":
            items.append(
                f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span> <span class=\"lane\">({lane})</span> <span class=\"result\">result={result}</span></li>"
            )
        elif kind == "approval_log":
            items.append(
                f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span> <span class=\"lane\">({lane})</span> <span class=\"actor\">by {actor}</span></li>"
            )
        else:
            items.append(
                f"<li><span class=\"ts\">{ts}</span> <span class=\"action\">{action}</span> <span class=\"lane\">({lane})</span> <span class=\"result\">result={result}</span></li>"
            )
    return "\n".join(items) if items else "<li>No entries available</li>"


def render_mission_control(
    operator_status: dict[str, Any],
    runtime_status: dict[str, Any],
    activity_entries: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    remediation_history: dict[str, Any],
    autonomy_policy: dict[str, Any],
    approval_history: dict[str, Any],
    approval_presets_payload: dict[str, Any],
    approval_expiry_payload: dict[str, Any],
    policy_drift_payload: dict[str, Any],
    remediation_queue_payload: dict[str, Any],
    remediation_audit_payload: dict[str, Any],
    approval_log_payload: dict[str, Any],
    runtime_decisions_payload: dict[str, Any],
) -> str:
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    details = operator_status.get("details") if isinstance(operator_status.get("details"), dict) else {}
    bridge = details.get("bridge_checks") if isinstance(details.get("bridge_checks"), dict) else {}
    return template.safe_substitute(
        system_health=escape(str(runtime_status.get("system_health", {}).get("status", "FAILED"))),
        ledger_status=escape(str(operator_status.get("ledger_status", "FAILED"))),
        epoch_id=escape(_epoch_id(runtime_status)),
        operator_overall=escape(str(operator_status.get("overall_status", "UNKNOWN"))),
        memory_status=escape(str(operator_status.get("memory_status", "UNAVAILABLE"))),
        api_server=escape(str(operator_status.get("api_server", "MISSING"))),
        redis=escape(str(operator_status.get("redis", "MISSING"))),
        bridge_consumer=escape(str(bridge.get("consumer", "unavailable"))),
        bridge_inflight=escape(str(bridge.get("inflight", "unavailable"))),
        bridge_outbox=escape(str(bridge.get("outbox", "unavailable"))),
        activity_items=_activity_html(activity_entries),
        alert_items=_alerts_html(alerts),
        remediation_summary=_remediation_summary_html(remediation_history),
        remediation_last_event=_remediation_last_event_html(remediation_history),
        remediation_timeline=_remediation_timeline_html(remediation_history),
        autonomy_policy_items=_autonomy_policy_html(autonomy_policy),
        approval_history_last_event=_approval_history_last_event_html(approval_history),
        approval_history_timeline=_approval_history_timeline_html(approval_history),
        approval_presets_items=_approval_presets_html(approval_presets_payload),
        approval_expiry_items=_approval_expiry_html(approval_expiry_payload),
        policy_drift_items=_policy_drift_html(policy_drift_payload),
        remediation_queue_items=_remediation_queue_html(remediation_queue_payload),
        remediation_audit_items=_audit_entries_html(remediation_audit_payload, kind="remediation_history"),
        approval_log_items=_audit_entries_html(approval_log_payload, kind="approval_log"),
        runtime_decision_items=_audit_entries_html(runtime_decisions_payload, kind="runtime_decisions"),
    )


async def health_endpoint(request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "mission_control", "port": SERVER_PORT})


async def operator_status_endpoint(request) -> JSONResponse:
    return JSONResponse(load_operator_status())


async def runtime_status_endpoint(request) -> JSONResponse:
    return JSONResponse(load_runtime_status())


async def activity_endpoint(request) -> JSONResponse:
    return JSONResponse(load_activity_entries())


async def proof_artifacts_endpoint(request) -> JSONResponse:
    limit_raw = request.query_params.get("limit", "50")
    try:
        limit = max(1, min(int(limit_raw), 200))
    except ValueError:
        limit = 50
    return JSONResponse(load_proof_artifacts(limit=limit))


async def proof_artifact_detail_endpoint(request) -> JSONResponse:
    artifact_id = str(request.path_params.get("artifact_id", "")).strip()
    if not artifact_id:
        return JSONResponse({"ok": False, "error": "missing_artifact_id"}, status_code=400)
    try:
        payload = load_proof_artifact_detail(artifact_id)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    if payload is None:
        return JSONResponse({"ok": False, "error": "not_found", "artifact_id": artifact_id}, status_code=404)
    return JSONResponse(payload)


async def alerts_endpoint(request) -> JSONResponse:
    limit_raw = request.query_params.get("limit", "100")
    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 100
    return JSONResponse({"alerts": load_alerts(limit=limit)})


async def remediation_history_endpoint(request) -> JSONResponse:
    lane = request.query_params.get("lane")
    if lane not in {None, "", "memory", "worker"}:
        lane = None
    last_raw = request.query_params.get("last")
    last = 100
    if last_raw:
        try:
            last = max(0, min(int(last_raw), 500))
        except ValueError:
            last = 100
    payload = load_remediation_audit_entries(last=last)
    # Preserve existing summary payload shape for backward compatibility.
    payload.update(load_remediation_history(lane=lane or None, last=last))
    return JSONResponse(payload)


async def autonomy_policy_endpoint(request) -> JSONResponse:
    lane = request.query_params.get("lane")
    if lane not in {None, "", "memory_recovery", "worker_recovery", "api_recovery", "redis_recovery"}:
        lane = None
    return JSONResponse(load_autonomy_policy(lane=lane or None))


async def approval_history_endpoint(request) -> JSONResponse:
    lane = request.query_params.get("lane")
    if lane not in {None, "", "memory_recovery", "worker_recovery", "api_recovery", "redis_recovery"}:
        lane = None
    last_raw = request.query_params.get("last")
    last: int | None = None
    if last_raw:
        try:
            last = max(0, min(int(last_raw), 500))
        except ValueError:
            last = None
    return JSONResponse(load_approval_history(lane=lane or None, last=last))


async def approval_log_endpoint(request) -> JSONResponse:
    last_raw = request.query_params.get("last")
    last = 100
    if last_raw:
        try:
            last = max(0, min(int(last_raw), 500))
        except ValueError:
            last = 100
    return JSONResponse(load_approval_log_entries(last=last))


async def runtime_decisions_endpoint(request) -> JSONResponse:
    last_raw = request.query_params.get("last")
    last = 100
    if last_raw:
        try:
            last = max(0, min(int(last_raw), 500))
        except ValueError:
            last = 100
    return JSONResponse(load_runtime_decisions(last=last))


async def qs_runs_endpoint(request) -> JSONResponse:
    limit_raw = request.query_params.get("limit", "100")
    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 100
    return JSONResponse(load_qs_runs(limit=limit))


async def qs_run_detail_endpoint(request) -> JSONResponse:
    run_id = str(request.path_params.get("run_id", "")).strip()
    if not run_id:
        return JSONResponse({"ok": False, "error": "missing_run_id"}, status_code=400)
    payload = load_qs_run(run_id)
    if payload is None:
        return JSONResponse({"ok": False, "error": "not_found", "run_id": run_id}, status_code=404)
    return JSONResponse(payload)


async def qs_run_artifacts_endpoint(request) -> JSONResponse:
    run_id = str(request.path_params.get("run_id", "")).strip()
    if not run_id:
        return JSONResponse({"ok": False, "error": "missing_run_id"}, status_code=400)
    payload = load_qs_run_artifacts(run_id)
    if payload is None:
        return JSONResponse({"ok": False, "error": "not_found", "run_id": run_id}, status_code=404)
    return JSONResponse(payload)

async def approval_presets_endpoint(request) -> JSONResponse:
    return JSONResponse(load_approval_presets())


async def approval_expiry_status_endpoint(request) -> JSONResponse:
    return JSONResponse(load_approval_expiry())


async def policy_drift_endpoint(request) -> JSONResponse:
    return JSONResponse(load_policy_drift())


async def decision_preview_endpoint(request) -> JSONResponse:
    return JSONResponse(load_decision_preview())


async def decisions_latest_endpoint(request) -> JSONResponse:
    return JSONResponse(load_latest_pending_decision())


async def decisions_history_endpoint(request) -> JSONResponse:
    raw_limit = request.query_params.get("limit", "50")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 50
    return JSONResponse(load_decision_history(limit=limit))


async def decisions_latest_suggestion_endpoint(request) -> JSONResponse:
    return JSONResponse(load_decision_suggestion())


async def decisions_latest_suggestion_feedback_endpoint(request) -> JSONResponse:
    return JSONResponse(load_decision_suggestion_feedback())


async def decisions_latest_policy_endpoint(request) -> JSONResponse:
    payload = load_decision_policy()
    latest, _error = _load_latest_decision_state()
    if isinstance(latest, dict):
        try:
            _record_policy_evaluation_if_needed(latest, payload)
            _record_auto_lane_freeze_if_needed(latest, payload)
        except DecisionPersistenceError:
            pass
    return JSONResponse(payload)


async def decisions_latest_auto_lane_review_endpoint(request) -> JSONResponse:
    return JSONResponse(load_auto_lane_review_payload())


async def decisions_auto_lane_candidates_endpoint(request) -> JSONResponse:
    raw_limit = request.query_params.get("limit", "10")
    try:
        limit = max(1, min(int(raw_limit), 50))
    except (TypeError, ValueError):
        limit = 10
    return JSONResponse(load_auto_lane_candidates_payload(limit=limit))


async def decisions_auto_lane_readiness_endpoint(request) -> JSONResponse:
    raw_recent_cases = request.query_params.get("recent_cases", "20")
    try:
        recent_cases = max(1, min(int(raw_recent_cases), 50))
    except (TypeError, ValueError):
        recent_cases = 20
    return JSONResponse(load_auto_lane_readiness_payload(recent_cases=recent_cases))


async def policy_stats_endpoint(request) -> JSONResponse:
    return JSONResponse(load_policy_stats_payload())


async def policy_review_endpoint(request) -> JSONResponse:
    return JSONResponse(load_policy_review_payload())


async def policy_tuning_preview_endpoint(request) -> JSONResponse:
    raw_alignment_threshold = request.query_params.get("alignment_threshold", "2")
    raw_confidence_requirement = request.query_params.get("confidence_requirement", "HIGH")
    raw_recent_cases = request.query_params.get("recent_cases", "20")
    try:
        return JSONResponse(
            load_policy_tuning_preview_payload(
                alignment_threshold=raw_alignment_threshold,
                confidence_requirement=raw_confidence_requirement,
                recent_cases=int(raw_recent_cases),
            )
        )
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


async def policy_preflight_endpoint(request) -> JSONResponse:
    component = str(request.query_params.get("component", "") or "")
    target_value = request.query_params.get("target_value")
    try:
        return JSONResponse(load_policy_preflight_payload(component=component, target_value=target_value))
    except (PolicyProposalError, RuntimeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


async def policy_proposals_endpoint(request) -> JSONResponse:
    if request.method == "GET":
        raw_limit = request.query_params.get("limit", "50")
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 50
        return JSONResponse(load_policy_change_proposals_payload(limit=limit))

    try:
        payload = await _optional_request_json(request)
        policy_component = payload.get("policy_component")
        proposed_value = payload.get("proposed_value")
        operator_note = payload.get("operator_note")
        if operator_note is not None and not isinstance(operator_note, str):
            raise RuntimeError("invalid_operator_note")
        current_review = load_policy_review_payload()
        simulation_reference = f"/api/policy/tuning-preview?success_threshold={proposed_value}"
        record = create_policy_change_proposal(
            _observability_root(),
            created_at=_utc_now_iso(),
            policy_component=str(policy_component or ""),
            proposed_value=proposed_value,
            evidence_summary=str(current_review.get("review_summary") or "insufficient evidence for strong review conclusions"),
            simulation_reference=simulation_reference,
            operator_note=operator_note,
        )
        return JSONResponse({"ok": True, "proposal": record})
    except (PolicyProposalError, RuntimeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


async def policy_proposal_detail_endpoint(request) -> JSONResponse:
    proposal_id = str(request.path_params.get("proposal_id") or "")
    payload = load_policy_change_proposal_detail_payload(proposal_id)
    if payload is None:
        return JSONResponse({"ok": False, "error": "proposal_not_found"}, status_code=404)
    return JSONResponse({"ok": True, "proposal": payload})


async def policy_proposal_approve_endpoint(request) -> JSONResponse:
    proposal_id = str(request.path_params.get("proposal_id") or "")
    try:
        payload = await _optional_request_json(request)
        operator_note = payload.get("operator_note")
        if operator_note is not None and not isinstance(operator_note, str):
            raise RuntimeError("invalid_operator_note")
        proposal = approve_policy_change_proposal(
            _observability_root(),
            proposal_id=proposal_id,
            created_at=_utc_now_iso(),
            operator_note=operator_note,
        )
        return JSONResponse({"ok": True, "proposal_id": proposal["proposal_id"], "status": proposal["status"]})
    except (PolicyProposalError, RuntimeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


async def policy_proposal_reject_endpoint(request) -> JSONResponse:
    proposal_id = str(request.path_params.get("proposal_id") or "")
    try:
        payload = await _optional_request_json(request)
        operator_note = payload.get("operator_note")
        if operator_note is not None and not isinstance(operator_note, str):
            raise RuntimeError("invalid_operator_note")
        proposal = reject_policy_change_proposal(
            _observability_root(),
            proposal_id=proposal_id,
            created_at=_utc_now_iso(),
            operator_note=operator_note,
        )
        return JSONResponse({"ok": True, "proposal_id": proposal["proposal_id"], "status": proposal["status"]})
    except (PolicyProposalError, RuntimeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


async def policy_proposal_deploy_endpoint(request) -> JSONResponse:
    proposal_id = str(request.path_params.get("proposal_id") or "")
    try:
        payload = await _optional_request_json(request)
        operator_note = payload.get("operator_note")
        if operator_note is not None and not isinstance(operator_note, str):
            raise RuntimeError("invalid_operator_note")
        proposal = load_policy_change_proposal_detail_payload(proposal_id)
        if proposal is None:
            raise PolicyProposalError("proposal_not_found")
        if str(proposal.get("status") or "") != "APPROVED_FOR_IMPLEMENTATION":
            raise PolicyProposalError("proposal_not_approved_for_implementation")
        preflight = load_policy_preflight_payload(
            component=str(proposal["policy_component"]),
            target_value=proposal["proposed_value"],
        )
        if not preflight.get("is_valid"):
            return JSONResponse({"ok": False, "error": "policy preflight failed", "preflight": preflight}, status_code=409)
        timestamp = _utc_now_iso()
        append_policy_deployment_event(
            _observability_root(),
            proposal_id=proposal_id,
            event="POLICY_DEPLOYMENT_REQUESTED",
            created_at=timestamp,
            operator_note=operator_note,
        )
        record = deploy_policy_version(
            _runtime_root(),
            _observability_root(),
            proposal_id=proposal_id,
            deployed_at=timestamp,
            policy_component=str(proposal["policy_component"]),
            new_value=float(proposal["proposed_value"]),
        )
        append_policy_deployment_event(
            _observability_root(),
            proposal_id=proposal_id,
            event="POLICY_DEPLOYED",
            created_at=timestamp,
            operator_note=operator_note,
        )
        return JSONResponse({"ok": True, **record})
    except (PolicyProposalError, RuntimeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


async def policy_version_endpoint(request) -> JSONResponse:
    return JSONResponse(load_policy_version_payload())


async def policy_versions_endpoint(request) -> JSONResponse:
    raw_limit = request.query_params.get("limit", "50")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 50
    return JSONResponse(load_policy_versions_payload(limit=limit))


async def policy_version_rollback_endpoint(request) -> JSONResponse:
    policy_version_id = str(request.path_params.get("policy_version_id") or "")
    try:
        payload = await _optional_request_json(request)
        operator_note = payload.get("operator_note")
        if operator_note is not None and not isinstance(operator_note, str):
            raise RuntimeError("invalid_operator_note")
        target = get_policy_version(_observability_root(), policy_version_id)
        if target is None:
            raise PolicyProposalError("rollback_target_version_not_found")
        preflight = load_policy_preflight_payload(
            component=str(target["policy_component"]),
            target_value=target["new_value"],
        )
        if not preflight.get("is_valid"):
            return JSONResponse({"ok": False, "error": "policy preflight failed", "preflight": preflight}, status_code=409)
        result = rollback_policy_version(
            _runtime_root(),
            _observability_root(),
            target_version_id=policy_version_id,
            rolled_back_at=_utc_now_iso(),
            operator_note=operator_note,
        )
        return JSONResponse({"ok": True, **result})
    except (PolicyProposalError, RuntimeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


async def policy_auto_lane_unfreeze_endpoint(request) -> JSONResponse:
    try:
        payload = await _optional_request_json(request)
        operator_note = payload.get("operator_note")
        if operator_note is not None and not isinstance(operator_note, str):
            raise RuntimeError("invalid_operator_note")
        result, error = _unfreeze_policy_auto_lane(operator_note=operator_note)
        if error:
            return JSONResponse({"ok": False, "error": error}, status_code=409)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


async def system_model_endpoint(request) -> JSONResponse:
    try:
        payload = load_system_model()
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "system_model_not_found"}, status_code=404)
    except (json.JSONDecodeError, OSError, RuntimeError):
        return JSONResponse({"ok": False, "error": "system_model_unreadable"}, status_code=500)
    return JSONResponse({"ok": True, "system_model": payload})


async def _optional_request_json(request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_json_body")
    return payload


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_latest_decision(
    *,
    operator_status: str,
    operator_note: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        latest = read_latest_decision(_runtime_root())
    except DecisionPersistenceError:
        return None, "decision_state_unreadable"
    if latest is None:
        return None, "no_pending_decision"
    if latest.get("operator_status") != "PENDING":
        return None, "decision_not_pending"
    try:
        updated = record_operator_decision(
            str(latest.get("decision_id") or ""),
            operator_status,
            _runtime_root(),
            _observability_root(),
            operator_note=operator_note,
        )
    except DecisionPersistenceError as exc:
        return None, str(exc)
    return _sanitize_decision_payload(updated), None


def _load_latest_decision_state() -> tuple[dict[str, Any] | None, str | None]:
    try:
        latest = read_latest_decision(_runtime_root())
    except DecisionPersistenceError:
        return None, "decision_state_unreadable"
    if latest is None:
        return None, "latest_decision_missing"
    return latest, None


def _execute_latest_decision() -> tuple[dict[str, Any] | None, str | None]:
    latest, error = _load_latest_decision_state()
    if error:
        return None, error
    try:
        return handoff_approved_decision(latest, observability_root=_observability_root()), None
    except ExecutionBridgeError as exc:
        return None, str(exc)


def _record_suggestion_feedback(
    latest: dict[str, Any],
    *,
    operator_action: str,
    suggestion_payload: dict[str, Any],
    policy_payload: dict[str, Any] | None = None,
) -> None:
    suggestion = str(suggestion_payload.get("suggestion") or "NO_ACTION_RECOMMENDED")
    if operator_action == "IGNORE_SUGGESTION":
        event = "SUGGESTION_IGNORED"
        alignment = "IGNORED_SUGGESTION"
    else:
        matched = (
            (operator_action == "RETRY_EXECUTION" and suggestion == "RETRY_RECOMMENDED")
            or (operator_action == "ESCALATE_ISSUE" and suggestion == "ESCALATION_RECOMMENDED")
        )
        event = "SUGGESTION_ACCEPTED" if matched else "SUGGESTION_OVERRIDDEN"
        alignment = "MATCHED_SUGGESTION" if matched else "OVERRIDDEN"

    append_suggestion_feedback(
        _observability_root(),
        {
            "event": event,
            "decision_id": latest.get("decision_id"),
            "trace_id": latest.get("trace_id"),
            "ts_utc": latest.get("ts_utc"),
            "signal_received": latest.get("signal_received"),
            "proposed_action": latest.get("proposed_action"),
            "evidence_refs": latest.get("evidence_refs"),
            "operator_status": latest.get("operator_status"),
            "operator_note": latest.get("operator_note"),
            "suggestion": suggestion,
            "confidence_band": suggestion_payload.get("confidence_band"),
            "operator_action": operator_action,
            "alignment": alignment,
        },
    )
    _record_policy_alignment_if_needed(
        latest,
        operator_action=operator_action,
        policy_payload=policy_payload or load_decision_policy(),
    )


def _latest_policy_event_for_decision(decision_id: str, event_name: str) -> dict[str, Any] | None:
    if not decision_id:
        return None
    try:
        rows = read_decision_history(_observability_root(), limit=200)
    except DecisionPersistenceError:
        return None
    latest: dict[str, Any] | None = None
    for row in rows:
        if row.get("decision_id") == decision_id and row.get("event") == event_name:
            latest = row
    return latest


def _record_policy_evaluation_if_needed(latest: dict[str, Any], policy_payload: dict[str, Any]) -> None:
    decision_id = str(latest.get("decision_id") or "")
    if not decision_id:
        return
    existing = _latest_policy_event_for_decision(decision_id, "POLICY_EVALUATED")
    signature = (
        policy_payload.get("policy_verdict"),
        policy_payload.get("suggestion"),
        policy_payload.get("confidence_band"),
        policy_payload.get("policy_reason"),
    )
    if existing is not None:
        existing_signature = (
            existing.get("policy_verdict"),
            existing.get("suggestion"),
            existing.get("confidence_band"),
            existing.get("policy_reason"),
        )
        if existing_signature == signature:
            return

    append_decision_event(
        _observability_root(),
        {
            "event": "POLICY_EVALUATED",
            "decision_id": latest.get("decision_id"),
            "trace_id": latest.get("trace_id"),
            "ts_utc": latest.get("ts_utc"),
            "signal_received": latest.get("signal_received"),
            "proposed_action": latest.get("proposed_action"),
            "evidence_refs": latest.get("evidence_refs"),
            "operator_status": latest.get("operator_status"),
            "operator_note": latest.get("operator_note"),
            "suggestion": policy_payload.get("suggestion"),
            "confidence_band": policy_payload.get("confidence_band"),
            "policy_verdict": policy_payload.get("policy_verdict"),
            "policy_reason": policy_payload.get("policy_reason"),
            "alignment_count": int(policy_payload.get("alignment_count") or 0),
        },
    )


def _record_auto_lane_freeze_if_needed(latest: dict[str, Any], policy_payload: dict[str, Any]) -> None:
    if policy_payload.get("auto_lane_state") != "AUTO_LANE_FROZEN":
        return
    safe_lane = policy_payload.get("policy_safe_lane_raw") or policy_payload.get("policy_safe_lane")
    if safe_lane != "SUPERVISED_RETRY":
        return
    decision_id = str(latest.get("decision_id") or "")
    if not decision_id:
        return
    existing = _latest_policy_event_for_decision(decision_id, "POLICY_AUTO_LANE_FROZEN")
    if existing is not None:
        return
    append_decision_event(
        _observability_root(),
        {
            "event": "POLICY_AUTO_LANE_FROZEN",
            "decision_id": latest.get("decision_id"),
            "trace_id": latest.get("trace_id"),
            "ts_utc": latest.get("ts_utc"),
            "signal_received": latest.get("signal_received"),
            "proposed_action": latest.get("proposed_action"),
            "evidence_refs": latest.get("evidence_refs"),
            "operator_status": latest.get("operator_status"),
            "operator_note": latest.get("operator_note"),
            "suggestion": policy_payload.get("suggestion"),
            "confidence_band": policy_payload.get("confidence_band"),
            "policy_verdict": policy_payload.get("policy_verdict"),
            "policy_reason": policy_payload.get("auto_lane_reason"),
            "alignment_count": int(policy_payload.get("alignment_count") or 0),
        },
    )


def _record_policy_alignment_if_needed(
    latest: dict[str, Any],
    *,
    operator_action: str,
    policy_payload: dict[str, Any],
) -> None:
    lane = str(policy_payload.get("policy_safe_lane") or "NONE")
    if operator_action == "RETRY_EXECUTION":
        matched = lane == "SUPERVISED_RETRY"
    elif operator_action == "ESCALATE_ISSUE":
        matched = lane == "SUPERVISED_ESCALATION"
    else:
        matched = False
    event_name = "POLICY_ALIGNMENT_MATCHED" if matched else "POLICY_ALIGNMENT_MISMATCHED"
    append_decision_event(
        _observability_root(),
        {
            "event": event_name,
            "decision_id": latest.get("decision_id"),
            "trace_id": latest.get("trace_id"),
            "ts_utc": latest.get("ts_utc"),
            "signal_received": latest.get("signal_received"),
            "proposed_action": latest.get("proposed_action"),
            "evidence_refs": latest.get("evidence_refs"),
            "operator_status": latest.get("operator_status"),
            "operator_note": latest.get("operator_note"),
            "suggestion": policy_payload.get("suggestion"),
            "confidence_band": policy_payload.get("confidence_band"),
            "operator_action": operator_action,
            "alignment": "MATCHED" if matched else "MISMATCHED",
            "policy_verdict": policy_payload.get("policy_verdict"),
            "policy_reason": policy_payload.get("policy_reason"),
            "alignment_count": int(policy_payload.get("alignment_count") or 0),
        },
    )


def _retryable_latest_decision_state() -> tuple[dict[str, Any] | None, str | None]:
    latest, error = _load_latest_decision_state()
    if error:
        return None, error
    if latest is None:
        return None, "latest_decision_missing"
    if latest.get("operator_status") != "APPROVED":
        return None, "latest_decision_not_approved"

    execution = reconcile_execution_outcome(
        latest,
        repo_root=ROOT,
        observability_root=_observability_root(),
    )
    if not isinstance(execution, dict):
        return None, "execution_outcome_not_retryable"

    outcome_status = str(execution.get("outcome_status") or "")
    if outcome_status not in RETRYABLE_OUTCOMES:
        return None, "execution_outcome_not_retryable"

    latest_with_execution = dict(latest)
    latest_with_execution["execution"] = execution
    return latest_with_execution, None


def _retry_latest_decision() -> tuple[dict[str, Any] | None, str | None]:
    latest, error = _retryable_latest_decision_state()
    if error:
        return None, error
    execution = latest.get("execution") or {}
    retry_count = int(execution.get("retry_count") or 0) + 1
    suggestion_payload = load_decision_suggestion()
    policy_payload = load_decision_policy()
    try:
        result = retry_approved_decision(
            latest,
            observability_root=_observability_root(),
            retry_count=retry_count,
        )
        _record_suggestion_feedback(
            latest,
            operator_action="RETRY_EXECUTION",
            suggestion_payload=suggestion_payload,
            policy_payload=policy_payload,
        )
        return result, None
    except ExecutionBridgeError as exc:
        return None, str(exc)
    except DecisionPersistenceError as exc:
        return None, str(exc)


def _latest_auto_retry_metadata(decision_id: str) -> dict[str, Any] | None:
    if not decision_id:
        return None
    try:
        rows = read_decision_history(_observability_root(), limit=200)
    except DecisionPersistenceError:
        return None

    latest: dict[str, Any] | None = None
    for row in rows:
        if row.get("decision_id") == decision_id and row.get("event") == "AUTO_RETRY_TRIGGERED":
            latest = row
    if latest is None:
        return None
    return {
        "policy_reason": latest.get("policy_reason"),
        "alignment_count": latest.get("alignment_count"),
    }


def _maybe_trigger_policy_auto_retry(latest: dict[str, Any]) -> dict[str, Any] | None:
    if latest.get("operator_status") != "APPROVED":
        return None
    decision_id = str(latest.get("decision_id") or "")
    if not decision_id or _latest_auto_retry_metadata(decision_id) is not None:
        return None

    execution = reconcile_execution_outcome(
        latest,
        repo_root=ROOT,
        observability_root=_observability_root(),
    )
    if not isinstance(execution, dict) or execution.get("outcome_status") != "EXECUTION_FAILED":
        return None

    policy = load_decision_policy()
    _record_policy_evaluation_if_needed(latest, policy)
    _record_auto_lane_freeze_if_needed(latest, policy)
    if (
        policy.get("policy_verdict") != "AUTO_ALLOWED"
        or policy.get("policy_safe_lane") != "SUPERVISED_RETRY"
        or policy.get("confidence_band") != "HIGH"
        or int(policy.get("alignment_count") or 0) < 2
    ):
        return None

    retry_count = int(execution.get("retry_count") or 0) + 1
    result = auto_retry_approved_decision(
        latest,
        observability_root=_observability_root(),
        retry_count=retry_count,
    )
    append_decision_event(
        _observability_root(),
        {
            "event": "AUTO_RETRY_TRIGGERED",
            "decision_id": latest.get("decision_id"),
            "trace_id": latest.get("trace_id"),
            "ts_utc": latest.get("ts_utc"),
            "signal_received": latest.get("signal_received"),
            "proposed_action": latest.get("proposed_action"),
            "evidence_refs": latest.get("evidence_refs"),
            "operator_status": latest.get("operator_status"),
            "operator_note": latest.get("operator_note"),
            "policy_reason": policy.get("policy_reason"),
            "confidence_band": policy.get("confidence_band"),
            "alignment_count": int(policy.get("alignment_count") or 0),
        },
    )
    return result


def _escalate_latest_decision() -> tuple[dict[str, Any] | None, str | None]:
    latest, error = _retryable_latest_decision_state()
    if error:
        return None, error
    execution = latest.get("execution") or {}
    escalation_count = int(execution.get("escalation_count") or 0) + 1
    outcome_status = str(execution.get("outcome_status") or "").replace("EXECUTION_", "").lower() or "unknown"
    suggestion_payload = load_decision_suggestion()
    policy_payload = load_decision_policy()
    try:
        result = escalate_approved_decision(
            latest,
            observability_root=_observability_root(),
            escalation_count=escalation_count,
            reason=f"execution {outcome_status}",
        )
        _record_suggestion_feedback(
            latest,
            operator_action="ESCALATE_ISSUE",
            suggestion_payload=suggestion_payload,
            policy_payload=policy_payload,
        )
        return result, None
    except ExecutionBridgeError as exc:
        return None, str(exc)
    except DecisionPersistenceError as exc:
        return None, str(exc)


def _ignore_latest_suggestion() -> tuple[dict[str, Any] | None, str | None]:
    latest, error = _load_latest_decision_state()
    if error:
        return None, error
    if latest is None:
        return None, "latest_decision_missing"
    suggestion_payload = load_decision_suggestion()
    policy_payload = load_decision_policy()
    try:
        _record_suggestion_feedback(
            latest,
            operator_action="IGNORE_SUGGESTION",
            suggestion_payload=suggestion_payload,
            policy_payload=policy_payload,
        )
    except DecisionPersistenceError as exc:
        return None, str(exc)
    return {
        "ok": True,
        "feedback": {
            "decision_id": latest.get("decision_id"),
            "suggestion": suggestion_payload.get("suggestion"),
            "confidence_band": suggestion_payload.get("confidence_band"),
            "operator_action": "IGNORE_SUGGESTION",
            "alignment": "IGNORED_SUGGESTION",
        },
    }, None


def _policy_audit_context() -> tuple[dict[str, Any] | None, str | None]:
    latest, error = _load_latest_decision_state()
    if error or latest is None:
        return None, "latest_decision_missing"
    return latest, None


def _unfreeze_policy_auto_lane(*, operator_note: str | None) -> tuple[dict[str, Any] | None, str | None]:
    stats = load_policy_stats_payload()
    if stats.get("auto_lane_state") != "AUTO_LANE_FROZEN":
        return None, "auto_lane_not_frozen"

    context, error = _policy_audit_context()
    if error or context is None:
        return None, error or "auto_lane_audit_context_missing"

    base_event = {
        "decision_id": context.get("decision_id"),
        "trace_id": context.get("trace_id"),
        "ts_utc": context.get("ts_utc"),
        "signal_received": context.get("signal_received"),
        "proposed_action": context.get("proposed_action"),
        "evidence_refs": context.get("evidence_refs"),
        "operator_status": context.get("operator_status"),
        "operator_note": operator_note,
        "policy_reason": "manual_policy_review_completed",
    }
    try:
        append_decision_event(
            _observability_root(),
            {
                "event": "POLICY_AUTO_LANE_UNFREEZE_REQUESTED",
                **base_event,
            },
        )
        append_decision_event(
            _observability_root(),
            {
                "event": "POLICY_AUTO_LANE_UNFROZEN",
                **base_event,
            },
        )
    except DecisionPersistenceError as exc:
        return None, str(exc)
    return {
        "ok": True,
        "auto_lane_state": "AUTO_LANE_ACTIVE",
        "reason": "manual_policy_review_completed",
        "operator_note": operator_note,
    }, None


async def decisions_latest_approve_endpoint(request) -> JSONResponse:
    try:
        payload = await _optional_request_json(request)
        operator_note = payload.get("operator_note")
        if operator_note is not None and not isinstance(operator_note, str):
            raise RuntimeError("invalid_operator_note")
        decision, error = _resolve_latest_decision(operator_status="APPROVED", operator_note=operator_note)
        if error:
            return JSONResponse({"ok": False, "error": error}, status_code=409)
        return JSONResponse({"ok": True, "decision": decision})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


async def decisions_latest_reject_endpoint(request) -> JSONResponse:
    try:
        payload = await _optional_request_json(request)
        operator_note = payload.get("operator_note")
        if operator_note is not None and not isinstance(operator_note, str):
            raise RuntimeError("invalid_operator_note")
        decision, error = _resolve_latest_decision(operator_status="REJECTED", operator_note=operator_note)
        if error:
            return JSONResponse({"ok": False, "error": error}, status_code=409)
        return JSONResponse({"ok": True, "decision": decision})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


async def decisions_latest_execute_endpoint(request) -> JSONResponse:
    result, error = _execute_latest_decision()
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=409)
    return JSONResponse(result)


async def decisions_latest_retry_endpoint(request) -> JSONResponse:
    result, error = _retry_latest_decision()
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=409)
    return JSONResponse(result)


async def decisions_latest_escalate_endpoint(request) -> JSONResponse:
    result, error = _escalate_latest_decision()
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=409)
    return JSONResponse(result)


async def decisions_latest_suggestion_ignore_endpoint(request) -> JSONResponse:
    result, error = _ignore_latest_suggestion()
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=409)
    return JSONResponse(result)


async def remediation_queue_endpoint(request) -> JSONResponse:
    return JSONResponse(load_remediation_queue())


async def remediation_queue_enqueue_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        lane = str(payload.get("lane", "")).strip()
        action = str(payload.get("action", "")).strip()
        result = enqueue_remediation_queue(lane=lane, action=action)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def _request_json(request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise RuntimeError("invalid_json_body")
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_json_body")
    return payload


async def approval_approve_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        result = apply_approval_action(
            lane=str(payload.get("lane", "")),
            actor=str(payload.get("actor", "")),
            approve=True,
            expires_at=payload.get("expires_at"),
        )
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def approval_revoke_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        result = apply_approval_action(
            lane=str(payload.get("lane", "")),
            actor=str(payload.get("actor", "")),
            revoke=True,
        )
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def approval_expiry_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        result = apply_approval_action(
            lane=str(payload.get("lane", "")),
            actor=str(payload.get("actor", "")),
            expires_at=payload.get("expires_at"),
            clear_expiry=bool(payload.get("clear_expiry")),
        )
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)

async def approval_presets_apply_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        preset = str(payload.get("preset", "")).strip()
        result = apply_approval_preset(preset=preset)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def approval_presets_reset_endpoint(request) -> JSONResponse:
    try:
        payload = await _request_json(request)
        preset = str(payload.get("preset", "")).strip()
        result = reset_approval_preset(preset=preset)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)]}, status_code=400)


async def root_endpoint(request) -> HTMLResponse:
    operator_status = load_operator_status()
    runtime_status = load_runtime_status()
    activity_entries = load_activity_entries()
    alerts = load_alerts()
    remediation_history = load_remediation_history(last=20)
    autonomy_policy = load_autonomy_policy()
    approval_history = load_approval_history(last=20)
    approval_presets_payload = load_approval_presets()
    approval_expiry_payload = load_approval_expiry()
    policy_drift_payload = load_policy_drift()
    remediation_queue_payload = load_remediation_queue()
    remediation_audit_payload = load_remediation_audit_entries(last=20)
    approval_log_payload = load_approval_log_entries(last=20)
    runtime_decisions_payload = load_runtime_decisions(last=20)
    return HTMLResponse(
        render_mission_control(
            operator_status,
            runtime_status,
            activity_entries,
            alerts,
            remediation_history,
            autonomy_policy,
            approval_history,
            approval_presets_payload,
            approval_expiry_payload,
            policy_drift_payload,
            remediation_queue_payload,
            remediation_audit_payload,
            approval_log_payload,
            runtime_decisions_payload,
        )
    )


def create_app():
    if FASTAPI_AVAILABLE:
        app = FastAPI(title="0luka Mission Control", version="0.1.0")
        app.add_api_route("/health", health_endpoint, methods=["GET"])
        app.add_api_route("/api/operator_status", operator_status_endpoint, methods=["GET"])
        app.add_api_route("/api/runtime_status", runtime_status_endpoint, methods=["GET"])
        app.add_api_route("/api/activity", activity_endpoint, methods=["GET"])
        app.add_api_route("/api/proof_artifacts", proof_artifacts_endpoint, methods=["GET"])
        app.add_api_route("/api/proof_artifacts/{artifact_id}", proof_artifact_detail_endpoint, methods=["GET"])
        app.add_api_route("/api/alerts", alerts_endpoint, methods=["GET"])
        app.add_api_route("/api/remediation_history", remediation_history_endpoint, methods=["GET"])
        app.add_api_route("/api/autonomy_policy", autonomy_policy_endpoint, methods=["GET"])
        app.add_api_route("/api/approval_history", approval_history_endpoint, methods=["GET"])
        app.add_api_route("/api/approval_presets", approval_presets_endpoint, methods=["GET"])
        app.add_api_route("/api/approval_expiry", approval_expiry_status_endpoint, methods=["GET"])
        app.add_api_route("/api/policy_drift", policy_drift_endpoint, methods=["GET"])
        app.add_api_route("/api/decision_preview", decision_preview_endpoint, methods=["GET"])
        app.add_api_route("/api/decisions/latest", decisions_latest_endpoint, methods=["GET"])
        app.add_api_route("/api/decisions/latest/suggestion", decisions_latest_suggestion_endpoint, methods=["GET"])
        app.add_api_route("/api/decisions/latest/suggestion-feedback", decisions_latest_suggestion_feedback_endpoint, methods=["GET"])
        app.add_api_route("/api/decisions/latest/policy", decisions_latest_policy_endpoint, methods=["GET"])
        app.add_api_route("/api/decisions/latest/auto-lane-review", decisions_latest_auto_lane_review_endpoint, methods=["GET"])
        app.add_api_route("/api/decisions/auto-lane-candidates", decisions_auto_lane_candidates_endpoint, methods=["GET"])
        app.add_api_route("/api/decisions/auto-lane-readiness", decisions_auto_lane_readiness_endpoint, methods=["GET"])
        app.add_api_route("/api/policy/stats", policy_stats_endpoint, methods=["GET"])
        app.add_api_route("/api/policy/review", policy_review_endpoint, methods=["GET"])
        app.add_api_route("/api/policy/tuning-preview", policy_tuning_preview_endpoint, methods=["GET"])
        app.add_api_route("/api/policy/preflight", policy_preflight_endpoint, methods=["GET"])
        app.add_api_route("/api/policy/proposals", policy_proposals_endpoint, methods=["GET", "POST"])
        app.add_api_route("/api/policy/proposals/{proposal_id}", policy_proposal_detail_endpoint, methods=["GET"])
        app.add_api_route("/api/policy/proposals/{proposal_id}/approve", policy_proposal_approve_endpoint, methods=["POST"])
        app.add_api_route("/api/policy/proposals/{proposal_id}/reject", policy_proposal_reject_endpoint, methods=["POST"])
        app.add_api_route("/api/policy/proposals/{proposal_id}/deploy", policy_proposal_deploy_endpoint, methods=["POST"])
        app.add_api_route("/api/policy/version", policy_version_endpoint, methods=["GET"])
        app.add_api_route("/api/policy/versions", policy_versions_endpoint, methods=["GET"])
        app.add_api_route("/api/policy/versions/{policy_version_id}/rollback", policy_version_rollback_endpoint, methods=["POST"])
        app.add_api_route("/api/policy/auto-lane/unfreeze", policy_auto_lane_unfreeze_endpoint, methods=["POST"])
        app.add_api_route("/api/decisions/history", decisions_history_endpoint, methods=["GET"])
        app.add_api_route("/api/decisions/latest/approve", decisions_latest_approve_endpoint, methods=["POST"])
        app.add_api_route("/api/decisions/latest/reject", decisions_latest_reject_endpoint, methods=["POST"])
        app.add_api_route("/api/decisions/latest/execute", decisions_latest_execute_endpoint, methods=["POST"])
        app.add_api_route("/api/decisions/latest/retry", decisions_latest_retry_endpoint, methods=["POST"])
        app.add_api_route("/api/decisions/latest/escalate", decisions_latest_escalate_endpoint, methods=["POST"])
        app.add_api_route("/api/decisions/latest/suggestion-feedback/ignore", decisions_latest_suggestion_ignore_endpoint, methods=["POST"])
        app.add_api_route("/api/system_model", system_model_endpoint, methods=["GET"])
        app.add_api_route("/api/approval_log", approval_log_endpoint, methods=["GET"])
        app.add_api_route("/api/runtime_decisions", runtime_decisions_endpoint, methods=["GET"])
        app.add_api_route("/api/remediation_queue", remediation_queue_endpoint, methods=["GET"])
        app.add_api_route("/api/qs_runs", qs_runs_endpoint, methods=["GET"])
        app.add_api_route("/api/qs_runs/{run_id}", qs_run_detail_endpoint, methods=["GET"])
        app.add_api_route("/api/qs_runs/{run_id}/artifacts", qs_run_artifacts_endpoint, methods=["GET"])
        app.add_api_route("/api/remediation_queue/enqueue", remediation_queue_enqueue_endpoint, methods=["POST"])
        app.add_api_route("/api/approval_presets/apply", approval_presets_apply_endpoint, methods=["POST"])
        app.add_api_route("/api/approval_presets/reset", approval_presets_reset_endpoint, methods=["POST"])
        app.add_api_route("/api/approval/approve", approval_approve_endpoint, methods=["POST"])
        app.add_api_route("/api/approval/revoke", approval_revoke_endpoint, methods=["POST"])
        app.add_api_route("/api/approval/expiry", approval_expiry_endpoint, methods=["POST"])
        app.add_api_route("/", root_endpoint, methods=["GET"], response_class=HTMLResponse)
        return app

    return FastAPI(
        routes=[
            Route("/health", health_endpoint),
            Route("/api/operator_status", operator_status_endpoint),
            Route("/api/runtime_status", runtime_status_endpoint),
            Route("/api/activity", activity_endpoint),
            Route("/api/proof_artifacts", proof_artifacts_endpoint),
            Route("/api/proof_artifacts/{artifact_id}", proof_artifact_detail_endpoint),
            Route("/api/alerts", alerts_endpoint),
            Route("/api/remediation_history", remediation_history_endpoint),
            Route("/api/autonomy_policy", autonomy_policy_endpoint),
            Route("/api/approval_history", approval_history_endpoint),
            Route("/api/approval_presets", approval_presets_endpoint),
            Route("/api/approval_expiry", approval_expiry_status_endpoint),
            Route("/api/policy_drift", policy_drift_endpoint),
            Route("/api/decision_preview", decision_preview_endpoint),
            Route("/api/decisions/latest", decisions_latest_endpoint),
            Route("/api/decisions/latest/suggestion", decisions_latest_suggestion_endpoint),
            Route("/api/decisions/latest/suggestion-feedback", decisions_latest_suggestion_feedback_endpoint),
            Route("/api/decisions/latest/policy", decisions_latest_policy_endpoint),
            Route("/api/decisions/latest/auto-lane-review", decisions_latest_auto_lane_review_endpoint),
            Route("/api/decisions/auto-lane-candidates", decisions_auto_lane_candidates_endpoint),
            Route("/api/decisions/auto-lane-readiness", decisions_auto_lane_readiness_endpoint),
            Route("/api/policy/stats", policy_stats_endpoint),
            Route("/api/policy/review", policy_review_endpoint),
            Route("/api/policy/tuning-preview", policy_tuning_preview_endpoint),
            Route("/api/policy/preflight", policy_preflight_endpoint),
            Route("/api/policy/proposals", policy_proposals_endpoint, methods=["GET", "POST"]),
            Route("/api/policy/proposals/{proposal_id}", policy_proposal_detail_endpoint),
            Route("/api/policy/proposals/{proposal_id}/approve", policy_proposal_approve_endpoint, methods=["POST"]),
            Route("/api/policy/proposals/{proposal_id}/reject", policy_proposal_reject_endpoint, methods=["POST"]),
            Route("/api/policy/proposals/{proposal_id}/deploy", policy_proposal_deploy_endpoint, methods=["POST"]),
            Route("/api/policy/version", policy_version_endpoint),
            Route("/api/policy/versions", policy_versions_endpoint),
            Route("/api/policy/versions/{policy_version_id}/rollback", policy_version_rollback_endpoint, methods=["POST"]),
            Route("/api/policy/auto-lane/unfreeze", policy_auto_lane_unfreeze_endpoint, methods=["POST"]),
            Route("/api/decisions/history", decisions_history_endpoint),
            Route("/api/decisions/latest/approve", decisions_latest_approve_endpoint, methods=["POST"]),
            Route("/api/decisions/latest/reject", decisions_latest_reject_endpoint, methods=["POST"]),
            Route("/api/decisions/latest/execute", decisions_latest_execute_endpoint, methods=["POST"]),
            Route("/api/decisions/latest/retry", decisions_latest_retry_endpoint, methods=["POST"]),
            Route("/api/decisions/latest/escalate", decisions_latest_escalate_endpoint, methods=["POST"]),
            Route("/api/decisions/latest/suggestion-feedback/ignore", decisions_latest_suggestion_ignore_endpoint, methods=["POST"]),
            Route("/api/system_model", system_model_endpoint),
            Route("/api/approval_log", approval_log_endpoint),
            Route("/api/runtime_decisions", runtime_decisions_endpoint),
            Route("/api/remediation_queue", remediation_queue_endpoint),
            Route("/api/qs_runs", qs_runs_endpoint),
            Route("/api/qs_runs/{run_id}", qs_run_detail_endpoint),
            Route("/api/qs_runs/{run_id}/artifacts", qs_run_artifacts_endpoint),
            Route("/api/remediation_queue/enqueue", remediation_queue_enqueue_endpoint, methods=["POST"]),
            Route("/api/approval_presets/apply", approval_presets_apply_endpoint, methods=["POST"]),
            Route("/api/approval_presets/reset", approval_presets_reset_endpoint, methods=["POST"]),
            Route("/api/approval/approve", approval_approve_endpoint, methods=["POST"]),
            Route("/api/approval/revoke", approval_revoke_endpoint, methods=["POST"]),
            Route("/api/approval/expiry", approval_expiry_endpoint, methods=["POST"]),
            Route("/", root_endpoint),
        ]
    )


app = create_app()


def main() -> int:
    import uvicorn

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
