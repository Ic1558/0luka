from core.replay_engine import replay_trace

# Maps mismatch_class → structured fix proposal
_FIX_MAP = {
    "none": {
        "action": "no_fix_needed",
        "description": "Trace is consistent. No changes required.",
        "steps": [],
    },
    "snapshot_missing": {
        "action": "locate_trace",
        "description": "Trace not found in activity feed.",
        "steps": [
            "Verify trace_id is correct",
            "Check observability/activity_feed.jsonl exists and is readable",
            "Re-run the original command with --apply to regenerate trace",
        ],
    },
    "evidence_missing": {
        "action": "re_emit_trace",
        "description": "Trace is missing required fields (task or result).",
        "steps": [
            "Inspect raw trace line in activity_feed.jsonl",
            "Check write_trace() call in orchestrator for the failing path",
            "Ensure all early-return paths emit full trace payload",
        ],
    },
    "rule_drift": {
        "action": "review_routing_rules",
        "description": "Agent assignment or semantic field is inconsistent with risk/type.",
        "steps": [
            "Review multi_agent_router._VALID_COMBOS against current policy",
            "Verify intent_router_runtime classification keywords",
            "Confirm risk_engine output matches task type",
            "Do NOT auto-patch — propose correction to operator",
        ],
    },
    "command_drift": {
        "action": "review_command_resolver",
        "description": "Command presence does not match result status.",
        "steps": [
            "Check command_resolver.py for ambiguous match logic",
            "Verify COMMANDS.md registry entry for this intent",
            "Confirm exec_wrapper returns command in result for success cases",
        ],
    },
    "scope_violation": {
        "action": "harden_scope_guard",
        "description": "Write task has no scope — immutable path check may have been bypassed.",
        "steps": [
            "Verify runtime_guard.validate_execution() is called before execution",
            "Confirm normalize_input() resolves scope from context.current_file or cwd",
            "Do NOT execute write without explicit scope",
        ],
    },
    "trace_corruption": {
        "action": "quarantine_trace",
        "description": "Trace line could not be parsed or is structurally invalid.",
        "steps": [
            "Quarantine the trace_id as unreliable",
            "Inspect raw line in activity_feed.jsonl for encoding or write errors",
            "Check trace_writer for concurrent write safety",
        ],
    },
}


def propose_fix(trace_id: str) -> dict:
    """
    Read-only: replay the trace and return a structured fix proposal.
    No execution. No auto-patch. No side effects.
    """
    replay = replay_trace(trace_id)
    mismatch = replay.get("mismatch_class", "none")
    fix = _FIX_MAP.get(mismatch, _FIX_MAP["evidence_missing"])

    return {
        "trace_id": trace_id,
        "replay_status": replay.get("replay_status"),
        "mismatch_class": mismatch,
        "reasons": replay.get("reasons", []),
        "proposal": {
            "action": fix["action"],
            "description": fix["description"],
            "steps": fix["steps"],
        },
        "summary": replay.get("summary"),
        "execution": "none — proposal only",
    }
