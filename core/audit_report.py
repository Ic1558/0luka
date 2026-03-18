"""
audit_report.py — Session-level audit report generator.

Safety:
  - read-only: no trace mutation, no dispatch, no policy change

Output contract:
  {
    "report_id": str,
    "generated_at": str,
    "trace_count": int,
    "status_counts": {str: int},
    "failure_rate": float,
    "notable_findings": [str],
    "replay_readiness": {"consistent": int, "inconsistent": int, "invalid": int, "unknown": int},
    "items": [trace summary, ...],   # up to 10 most recent
  }
"""

import uuid
from datetime import datetime, timezone

from core.trace_inspector import list_traces
from core.replay_engine import replay_trace


def generate_report(limit: int = 50) -> dict:
    """
    Summarise recent traces into a structured audit report.

    Args:
        limit: Number of most-recent traces to analyse (default 50).

    Returns:
        Structured audit report dict.
    """
    report_id = str(uuid.uuid4())[:8]
    generated_at = datetime.now(timezone.utc).isoformat()

    inspection = list_traces(limit=limit)
    traces = inspection.get("traces", [])
    trace_count = len(traces)

    # --- status counts ---
    status_counts: dict = {}
    for t in traces:
        s = t.get("result_status") or "unknown"
        status_counts[s] = status_counts.get(s, 0) + 1

    # --- failure rate ---
    failure_statuses = {"rejected", "blocked", "failed"}
    failure_total = sum(
        count for status, count in status_counts.items()
        if status in failure_statuses
    )
    failure_rate = round(failure_total / trace_count, 3) if trace_count else 0.0

    # --- replay readiness (sample up to 10 most recent) ---
    replay_readiness = {"consistent": 0, "inconsistent": 0, "invalid": 0, "unknown": 0}
    for t in traces[:10]:
        tid = t.get("trace_id")
        if not tid:
            replay_readiness["unknown"] += 1
            continue
        try:
            r = replay_trace(tid)
            status = r.get("replay_status", "unknown")
            if status in replay_readiness:
                replay_readiness[status] += 1
            else:
                replay_readiness["unknown"] += 1
        except Exception:
            replay_readiness["unknown"] += 1

    # --- notable findings ---
    findings = []

    if failure_rate > 0.5:
        findings.append(
            f"high failure rate: {failure_rate:.0%} of {trace_count} traces rejected/blocked/failed"
        )

    rejected = status_counts.get("rejected", 0)
    blocked = status_counts.get("blocked", 0)
    if rejected + blocked > 0:
        findings.append(
            f"{rejected} rejected, {blocked} blocked in last {trace_count} traces"
        )

    if replay_readiness["invalid"] > 0:
        findings.append(
            f"{replay_readiness['invalid']} trace(s) replay-invalid (snapshot or version issue)"
        )

    no_snap = sum(1 for t in traces if not t.get("has_snapshot"))
    if no_snap > 0:
        findings.append(f"{no_snap} trace(s) missing snapshot — not replay-safe")

    if not findings:
        findings.append("no notable findings — traces appear nominal")

    return {
        "report_id": report_id,
        "generated_at": generated_at,
        "trace_count": trace_count,
        "status_counts": status_counts,
        "failure_rate": failure_rate,
        "notable_findings": findings,
        "replay_readiness": replay_readiness,
        "items": traces[:10],
    }
