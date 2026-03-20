"""
hindsight_engine.py — Analyzes completed traces and returns structured findings.

Output contract:
  {
    "trace_id": str,
    "hindsight_status": "success_analyzed" | "failure_analyzed" | "not_found" | "analyzed",
    "findings": {
      "failure_root_cause": str (if failed),
      "success_pattern": dict (if succeeded),
      "optimization_hint": [str] (always, may be empty),
    },
    "recommendations": [str],
  }
"""

from core.replay_engine import load_trace, replay_trace


def analyze_trace(trace_id: str) -> dict:
    """
    Analyze a completed trace and return structured hindsight output.

    Args:
        trace_id: The trace_id to analyze.

    Returns:
        Structured hindsight dict with findings and recommendations.
    """
    trace = load_trace(trace_id)

    if trace is None:
        return {
            "trace_id": trace_id,
            "hindsight_status": "not_found",
            "findings": {},
            "recommendations": ["trace not found — verify trace_id or check feed path"],
        }

    replay = replay_trace(trace_id)
    result = trace.get("result") or {}
    result_status = result.get("status", "unknown")
    task = trace.get("normalized_task") or {}
    task_type = task.get("type", "unknown")
    decision = trace.get("decision") or {}
    skill_route = decision.get("skill_route") or {}

    findings = {}

    # --- failure classification ---
    if replay["replay_status"] == "invalid":
        findings["failure_root_cause"] = replay.get("mismatch_class", "trace_invalid")
    elif result_status in ("rejected", "blocked"):
        findings["failure_root_cause"] = result.get("reason", "unknown_rejection")

    # --- success pattern ---
    if result_status in ("success", "planned") and replay["replay_status"] == "consistent":
        findings["success_pattern"] = {
            "task_type": task_type,
            "skill_id": decision.get("skill_id"),
            "capability": decision.get("capability"),
            "agent": (decision.get("agent") or {}).get("agent"),
            "result_status": result_status,
        }

    # --- optimization hints ---
    hints = []
    if task_type == "unknown":
        hints.append("intent_classification_weak")
    if skill_route.get("fallback"):
        hints.append("skill_routing_fallback")
    root = findings.get("failure_root_cause", "")
    if root == "destructive_intent":
        hints.append("destructive_intent_blocked_safely")
    if root in ("trace_corruption", "snapshot_corruption", "unsupported_trace_version"):
        hints.append("trace_integrity_issue")
    findings["optimization_hint"] = hints

    # --- recommendations ---
    recommendations = []
    if "failure_root_cause" in findings:
        r = findings["failure_root_cause"]
        if r == "destructive_intent":
            recommendations.append("clarify intent to non-destructive scope")
        elif r == "unknown_intent":
            recommendations.append("rephrase with clearer action keyword (verb + object)")
        elif r in ("trace_corruption", "snapshot_corruption", "unsupported_trace_version"):
            recommendations.append(f"trace integrity issue ({r}) — re-run operation")
        else:
            recommendations.append(f"review rejection reason: {r}")

    if "success_pattern" in findings:
        skill = findings["success_pattern"].get("skill_id")
        if skill:
            recommendations.append(f"pattern established: route similar intents to {skill}")

    if not recommendations:
        recommendations.append("no actionable finding — trace appears nominal")

    hindsight_status = (
        "success_analyzed" if "success_pattern" in findings
        else "failure_analyzed" if "failure_root_cause" in findings
        else "analyzed"
    )

    return {
        "trace_id": trace_id,
        "hindsight_status": hindsight_status,
        "findings": findings,
        "recommendations": recommendations,
    }
