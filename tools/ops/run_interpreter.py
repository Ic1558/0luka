from __future__ import annotations

from typing import Any


EXPECTED_ARTIFACT_TYPES = ("proof_pack", "ledger_proof_export")


def _artifact_id_for(run_id: str, artifact_type: str) -> str:
    return f"{artifact_type}:{run_id}"


def _normalize_artifacts(run_id: str, artifacts: Any) -> tuple[list[str], bool] | None:
    if not isinstance(artifacts, list):
        return None

    valid: list[str] = []
    seen: set[str] = set()
    inconsistent = False
    expected_set = {_artifact_id_for(run_id, artifact_type) for artifact_type in EXPECTED_ARTIFACT_TYPES}

    for item in artifacts:
        if not isinstance(item, str) or not item.strip():
            return None
        artifact_id = item.strip()
        if artifact_id in seen:
            inconsistent = True
            continue
        seen.add(artifact_id)
        if artifact_id not in expected_set:
            inconsistent = True
            continue
        valid.append(artifact_id)

    return sorted(valid), inconsistent


def interpret_run(run: Any, artifacts: Any) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None

    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return None
    run_id = run_id.strip()

    normalized = _normalize_artifacts(run_id, artifacts)
    if normalized is None:
        return None
    present_artifacts, inconsistent = normalized

    expected_artifacts = [_artifact_id_for(run_id, artifact_type) for artifact_type in EXPECTED_ARTIFACT_TYPES]
    missing_artifacts = [artifact_id for artifact_id in expected_artifacts if artifact_id not in present_artifacts]

    if inconsistent:
        signal = "INCONSISTENT"
    elif not present_artifacts:
        signal = "MISSING_PROOF"
    elif missing_artifacts:
        signal = "PARTIAL"
    else:
        signal = "COMPLETE"

    return {
        "run_id": run_id,
        "artifact_count": len(present_artifacts),
        "expected_artifacts": expected_artifacts,
        "missing_artifacts": missing_artifacts,
        "signal": signal,
    }
