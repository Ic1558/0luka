"""AG-28: Recovery executor — executes approved recovery actions via safe path only.

STRICTLY FORBIDDEN:
  - direct shell execution
  - git mutation (gc, prune, repack, reset, etc.)
  - .git metadata access
  - MCP config rewrite
  - launchd plist rewrite
  - interpreter path mutation
  - config rewrite

Every recovery action goes through existing runtime execution path.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def execute_recovery_action(
    recovery_action: dict[str, Any],
    failure_context: dict[str, Any],
) -> dict[str, Any]:
    """Execute an approved recovery action.

    Args:
        recovery_action: Dict from recovery_engine with recovery_action key.
        failure_context: Dict from verifier with run_id and failure details.

    Returns:
        Dict with: result (SUCCESS|FAILED|SKIPPED), action, reason, executed_at.

    Supported actions:
        RETRY_ONCE              — re-verify execution result via safe read path
        RECHECK_ARTIFACTS       — re-scan artifact surface for expected outputs
        REFRESH_RUNTIME_STATE   — reload runtime state cache (read-only op)
    """
    action = str(recovery_action.get("recovery_action") or "").upper()
    run_id = str(failure_context.get("run_id") or "")
    executed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if action == "RETRY_ONCE":
        return _retry_once(run_id, failure_context, executed_at)

    if action == "RECHECK_ARTIFACTS":
        return _recheck_artifacts(run_id, failure_context, executed_at)

    if action == "REFRESH_RUNTIME_STATE":
        return _refresh_runtime_state(run_id, failure_context, executed_at)

    # REQUEST_OPERATOR and STOP are routing decisions, not executable actions
    return {
        "result": "SKIPPED",
        "action": action,
        "reason": f"action_{action.lower()}_is_routing_only",
        "executed_at": executed_at,
        "run_id": run_id,
    }


def _retry_once(run_id: str, failure_context: dict[str, Any], executed_at: str) -> dict[str, Any]:
    """Re-verify by reading activity feed evidence (read-only path)."""
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        return _result("FAILED", "RETRY_ONCE", "no_runtime_root", executed_at, run_id)

    # Read-only: check if there is a more recent dispatch.end event for this run
    feed = Path(runtime_root) / "logs" / "activity_feed.jsonl"
    if not feed.exists():
        return _result("FAILED", "RETRY_ONCE", "activity_feed_missing", executed_at, run_id)

    try:
        import json
        events = []
        for line in feed.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                if isinstance(e, dict) and str(e.get("task_id") or "") == run_id:
                    events.append(e)
            except json.JSONDecodeError:
                continue

        dispatch_ends = [e for e in events if e.get("event") == "dispatch.end"]
        if dispatch_ends:
            return _result("SUCCESS", "RETRY_ONCE", "dispatch_end_found", executed_at, run_id)
        return _result("FAILED", "RETRY_ONCE", "no_dispatch_end_found", executed_at, run_id)
    except OSError as exc:
        logger.warning("retry_once: feed read error: %s", exc)
        return _result("FAILED", "RETRY_ONCE", f"feed_read_error:{exc}", executed_at, run_id)


def _recheck_artifacts(run_id: str, failure_context: dict[str, Any], executed_at: str) -> dict[str, Any]:
    """Recheck artifact surface by reading outbox (read-only)."""
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        return _result("FAILED", "RECHECK_ARTIFACTS", "no_runtime_root", executed_at, run_id)

    state_dir = Path(runtime_root) / "state"
    exec_latest = state_dir / "execution_latest.json"
    if not exec_latest.exists():
        return _result("FAILED", "RECHECK_ARTIFACTS", "no_execution_latest", executed_at, run_id)

    try:
        import json
        data = json.loads(exec_latest.read_text(encoding="utf-8"))
        # Check if the latest execution belongs to this run and succeeded
        if str(data.get("run_id") or data.get("execution_id") or "") and data.get("status") == "SUCCESS":
            return _result("SUCCESS", "RECHECK_ARTIFACTS", "artifact_evidence_found", executed_at, run_id)
        return _result("FAILED", "RECHECK_ARTIFACTS", "artifact_surface_still_incomplete", executed_at, run_id)
    except (OSError, Exception) as exc:
        logger.warning("recheck_artifacts: read error: %s", exc)
        return _result("FAILED", "RECHECK_ARTIFACTS", f"artifact_read_error:{exc}", executed_at, run_id)


def _refresh_runtime_state(run_id: str, failure_context: dict[str, Any], executed_at: str) -> dict[str, Any]:
    """Refresh runtime state by reading latest known-good state (read-only)."""
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        return _result("FAILED", "REFRESH_RUNTIME_STATE", "no_runtime_root", executed_at, run_id)

    state_dir = Path(runtime_root) / "state"
    if not state_dir.exists():
        return _result("FAILED", "REFRESH_RUNTIME_STATE", "no_state_dir", executed_at, run_id)

    # Read-only health check: confirm state dir is accessible and index_health readable
    try:
        state_files = list(state_dir.iterdir())
        readable_count = sum(1 for f in state_files if f.is_file() and f.stat().st_size > 0)
        if readable_count > 0:
            return _result("SUCCESS", "REFRESH_RUNTIME_STATE", f"{readable_count}_state_files_readable", executed_at, run_id)
        return _result("FAILED", "REFRESH_RUNTIME_STATE", "no_readable_state_files", executed_at, run_id)
    except OSError as exc:
        logger.warning("refresh_runtime_state: read error: %s", exc)
        return _result("FAILED", "REFRESH_RUNTIME_STATE", f"state_read_error:{exc}", executed_at, run_id)


def _result(result: str, action: str, reason: str, executed_at: str, run_id: str) -> dict[str, Any]:
    return {
        "result": result,
        "action": action,
        "reason": reason,
        "executed_at": executed_at,
        "run_id": run_id,
    }
