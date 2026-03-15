"""Shared reader helpers for AG-17C1 dual-read logic."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _get_execution_envelope(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    envelope = result.get("execution_envelope")
    return envelope if isinstance(envelope, dict) else None


def get_result_status(result: Dict[str, Any]) -> Optional[str]:
    envelope = _get_execution_envelope(result)
    if envelope:
        status = envelope.get("result", {}).get("status")
        if isinstance(status, str) and status.strip():
            return status
    return None


def get_result_summary(result: Dict[str, Any]) -> Optional[str]:
    envelope = _get_execution_envelope(result)
    if envelope:
        summary = envelope.get("result", {}).get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary
    return None


def get_result_provenance_hashes(result: Dict[str, Any]) -> Dict[str, Any]:
    envelope = _get_execution_envelope(result)
    if envelope:
        prov = envelope.get("provenance") or {}
        if isinstance(prov, dict):
            return {
                "inputs_sha256": str(prov.get("inputs_sha256") or ""),
                "outputs_sha256": str(prov.get("outputs_sha256") or ""),
                "envelope_sha256": str(prov.get("envelope_sha256") or ""),
            }
    return {"inputs_sha256": "", "outputs_sha256": "", "envelope_sha256": ""}


def get_result_seal(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    envelope = _get_execution_envelope(result)
    if envelope:
        seal = envelope.get("seal")
        if isinstance(seal, dict):
            return seal
    return None


def get_result_execution_events(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    envelope = _get_execution_envelope(result)
    if envelope:
        evidence = envelope.get("evidence", {})
        events = evidence.get("execution_events")
        if isinstance(events, list):
            return [event for event in events if isinstance(event, dict)]
    return []


def get_result_executor_identity(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    envelope = _get_execution_envelope(result)
    if envelope:
        executor = envelope.get("executor")
        if isinstance(executor, dict):
            return executor
    return None


def get_result_routing(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    envelope = _get_execution_envelope(result)
    if envelope:
        routing = envelope.get("routing")
        if isinstance(routing, dict):
            return routing
    return None


def get_result_policy(result: Dict[str, Any]) -> Dict[str, Any]:
    envelope = _get_execution_envelope(result)
    if envelope:
        policy = envelope.get("policy")
        if isinstance(policy, dict):
            return policy
    return {}


def _normalize_hashes(hashes: Dict[str, Any]) -> Dict[str, str]:
    return {k: str(v) for k, v in hashes.items() if isinstance(v, str)}


def detect_result_authority_mismatches(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    mismatches: List[Dict[str, Any]] = []
    envelope = _get_execution_envelope(result)
    if not envelope:
        return mismatches

    env_result = envelope.get("result", {})
    if env_result.get("status") and env_result.get("status") != result.get("status"):
        mismatches.append({"field": "status", "envelope": env_result.get("status"), "legacy": result.get("status")})
    if env_result.get("summary") and env_result.get("summary") != result.get("summary"):
        mismatches.append({"field": "summary", "envelope": env_result.get("summary"), "legacy": result.get("summary")})

    env_hashes = get_result_provenance_hashes({"execution_envelope": envelope})
    legacy_hashes = get_result_provenance_hashes({k: v for k, v in result.items() if k != "execution_envelope"})
    for key in {"inputs_sha256", "outputs_sha256"}:
        if env_hashes.get(key) and env_hashes.get(key) != legacy_hashes.get(key):
            mismatches.append({"field": f"provenance.{key}", "envelope": env_hashes.get(key), "legacy": legacy_hashes.get(key)})

    env_seal = envelope.get("seal")
    if isinstance(env_seal, dict) and isinstance(result.get("seal"), dict):
        mismatches.append(
            {
                "field": "seal_schema",
                "kind": "informational",
                "message": "legacy and envelope seals use intentionally different schemas",
            }
        )

    return mismatches
