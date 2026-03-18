"""
auto_suggestion.py — Generates actionable next-step suggestions from hindsight results.

Output contract:
  {
    "trace_id": str,
    "hindsight_status": str,
    "suggestions": [
      {
        "type": "better_routing" | "better_skill_choice" | "safer_next_action" | "operator_review",
        "rationale": str,
        "confidence": float,
      }
    ],
  }
"""

from core.hindsight_engine import analyze_trace


def generate_suggestions(hindsight_result: dict) -> dict:
    """
    Generate structured actionable suggestions from a hindsight result.

    Args:
        hindsight_result: Output of analyze_trace().

    Returns:
        Structured suggestion dict.
    """
    trace_id = hindsight_result.get("trace_id")
    findings = hindsight_result.get("findings") or {}
    status = hindsight_result.get("hindsight_status", "unknown")

    suggestions = []

    # --- optimization hints → routing/skill suggestions ---
    for hint in findings.get("optimization_hint", []):
        if hint == "intent_classification_weak":
            suggestions.append({
                "type": "better_routing",
                "rationale": "intent classified as unknown — use explicit action keyword (e.g. 'list', 'check', 'analyze')",
                "confidence": 0.7,
            })
        elif hint == "skill_routing_fallback":
            suggestions.append({
                "type": "better_skill_choice",
                "rationale": "no skill matched intent — add domain keyword to trigger skill routing",
                "confidence": 0.6,
            })
        elif hint == "trace_integrity_issue":
            suggestions.append({
                "type": "operator_review",
                "rationale": "trace integrity issue detected — operator should verify feed and snapshot",
                "confidence": 1.0,
            })

    # --- failure root cause → specific suggestions ---
    root = findings.get("failure_root_cause")
    if root == "destructive_intent":
        suggestions.append({
            "type": "safer_next_action",
            "rationale": "destructive intent blocked — scope down the request or confirm with operator before retrying",
            "confidence": 0.9,
        })
    elif root == "unknown_intent":
        suggestions.append({
            "type": "better_routing",
            "rationale": "intent not recognized — rephrase as verb + object (e.g. 'list files', 'check health')",
            "confidence": 0.75,
        })
    elif root in ("trace_corruption", "snapshot_corruption", "unsupported_trace_version"):
        suggestions.append({
            "type": "operator_review",
            "rationale": f"trace integrity failure: {root} — re-run the original operation",
            "confidence": 1.0,
        })
    elif root and root not in ("destructive_intent", "unknown_intent"):
        suggestions.append({
            "type": "operator_review",
            "rationale": f"unrecognized rejection reason: {root} — operator review recommended",
            "confidence": 0.5,
        })

    # --- success pattern → reinforcement suggestion ---
    success = findings.get("success_pattern")
    if success:
        skill = success.get("skill_id")
        capability = success.get("capability")
        if skill:
            suggestions.append({
                "type": "better_skill_choice",
                "rationale": f"successful execution via {skill}:{capability} — reuse this pattern for similar intents",
                "confidence": 0.8,
            })

    # --- fallback if no suggestions generated ---
    if not suggestions:
        suggestions.append({
            "type": "operator_review",
            "rationale": "no clear improvement pattern identified — operator review recommended",
            "confidence": 0.5,
        })

    return {
        "trace_id": trace_id,
        "hindsight_status": status,
        "suggestions": suggestions,
    }


def suggest_for_trace(trace_id: str) -> dict:
    """
    Convenience: run hindsight + suggestion in one call.

    Args:
        trace_id: The trace_id to analyze and suggest for.

    Returns:
        Suggestion dict.
    """
    hindsight = analyze_trace(trace_id)
    return generate_suggestions(hindsight)
