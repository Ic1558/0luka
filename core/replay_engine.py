import json
from pathlib import Path

from core.config import RUNTIME_LOGS_DIR
from core.snapshot_store import load_snapshot
from core.trace_versioning import is_supported, get_version_handler

TRACE_FILE = RUNTIME_LOGS_DIR / "activity_feed.jsonl"

# Known valid type/risk/agent combinations
_VALID_COMBOS = {
    ("read", "low"): "liam",
    ("write", "medium"): "lisa",
    ("write", "low"): "lisa",
    ("write", "high"): "gmx",
    ("verify", "low"): "vera",
    ("verify", "medium"): "vera",
    ("unknown", "medium"): "system",
}


def load_trace(trace_id: str):

    if not TRACE_FILE.exists():
        return None

    with open(TRACE_FILE, "r") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("trace_id") == trace_id:
                    return data
            except json.JSONDecodeError:
                continue

    return None


def _classify_mismatch(reasons: list) -> str:
    if not reasons:
        return "none"
    tags = set(reasons)
    if "trace_corrupt" in tags:
        return "trace_corruption"
    if "missing_result" in tags or "missing_task" in tags:
        return "evidence_missing"
    if "command_missing_for_success" in tags:
        return "command_drift"
    if "semantic_contradiction" in tags:
        return "rule_drift"
    if "agent_mismatch" in tags:
        return "rule_drift"
    if "scope_missing_on_write" in tags:
        return "scope_violation"
    return "evidence_missing"


def replay_trace(trace_id: str):

    trace = load_trace(trace_id)

    if trace is None:
        return {
            "trace_id": trace_id,
            "replay_status": "invalid",
            "mismatch_class": "snapshot_missing",
            "reasons": ["trace not found in feed"],
            "summary": None,
        }

    # --- version field existence and type check ---
    raw_version = trace.get("trace_version")
    if raw_version is None or not isinstance(raw_version, str):
        return {
            "trace_id": trace_id,
            "replay_status": "invalid",
            "mismatch_class": "trace_corruption",
            "reasons": ["missing or malformed trace_version"],
            "summary": None,
        }

    # --- version support check ---
    if not is_supported(raw_version):
        return {
            "trace_id": trace_id,
            "replay_status": "invalid",
            "mismatch_class": "unsupported_trace_version",
            "reasons": [f"trace_version '{raw_version}' is not supported"],
            "summary": None,
        }

    # --- version-specific validation ---
    handler = get_version_handler(raw_version)
    if handler is None:
        return {
            "trace_id": trace_id,
            "replay_status": "invalid",
            "mismatch_class": "unsupported_trace_version",
            "reasons": [f"no handler for trace_version '{raw_version}'"],
            "summary": None,
        }

    missing = handler["validate"](trace)
    if missing:
        return {
            "trace_id": trace_id,
            "replay_status": "invalid",
            "mismatch_class": "trace_corruption",
            "reasons": [f"missing required field(s): {missing}"],
            "summary": None,
        }

    # --- execution_mode present (required for all versions) ---
    if not trace.get("execution_mode"):
        return {
            "trace_id": trace_id,
            "replay_status": "invalid",
            "mismatch_class": "trace_corruption",
            "reasons": ["missing execution_mode"],
            "summary": None,
        }

    # --- snapshot integrity check ---
    snapshot = load_snapshot(trace_id)
    if snapshot is None:
        return {
            "trace_id": trace_id,
            "replay_status": "invalid",
            "mismatch_class": "snapshot_corruption",
            "reasons": ["snapshot missing for trace"],
            "summary": None,
        }
    if not isinstance(snapshot.get("state_before"), dict) or not isinstance(snapshot.get("state_after"), dict):
        return {
            "trace_id": trace_id,
            "replay_status": "invalid",
            "mismatch_class": "snapshot_corruption",
            "reasons": ["snapshot malformed: missing state_before or state_after"],
            "summary": None,
        }

    reasons = []
    task = trace.get("normalized_task") or {}
    result = trace.get("result") or {}
    command = trace.get("command")
    decision = trace.get("decision") or {}
    risk = decision.get("risk") or {}
    agent = decision.get("agent") or {}

    task_type = task.get("type")
    risk_level = risk.get("risk_level") or task.get("risk") or "unknown"
    agent_name = agent.get("agent") or ("system" if task_type == "unknown" else "unknown")
    result_status = result.get("status")

    # --- required fields ---
    if not task:
        reasons.append("missing_task")
    if not result:
        reasons.append("missing_result")

    # --- semantic: result=success requires command ---
    if result_status == "success" and not command:
        reasons.append("command_missing_for_success")

    # --- semantic: rejected/unknown should not have real command ---
    if result_status == "rejected" and command and command.get("name"):
        reasons.append("semantic_contradiction")

    # --- agent cross-check ---
    if task_type and risk_level:
        expected_agent = _VALID_COMBOS.get((task_type, risk_level))
        if expected_agent and agent_name and agent_name != expected_agent:
            reasons.append("agent_mismatch")

    # --- scope check for writes ---
    if task_type == "write" and not task.get("scope"):
        reasons.append("scope_missing_on_write")

    # --- replay status ---
    if not reasons:
        replay_status = "consistent"
    elif "missing_task" in reasons or "missing_result" in reasons:
        replay_status = "invalid"
    else:
        replay_status = "inconsistent"

    return {
        "trace_id": trace_id,
        "replay_status": replay_status,
        "mismatch_class": _classify_mismatch(reasons),
        "reasons": reasons,
        "summary": {
            "task_type": task_type,
            "risk_level": risk_level,
            "agent": agent_name,
            "result_status": result_status,
            "command": command.get("name") if command else None,
            "snapshot": {
                "state_before": snapshot["state_before"],
                "state_after": snapshot["state_after"],
            },
        },
    }
