"""
paula_readiness.py — Paula input readiness checker.

Invariants:
  - Read-only: no live trading, no order execution, no policy mutation
  - No fake "ready" if signal/input is absent
  - Explicit blockers reported

Output contract:
  {
    "input_available": bool,
    "signal_source_status": "available" | "stale" | "missing",
    "paula_ready": bool,
    "blockers": [str],
    "checked_at": str,
  }
"""

from datetime import datetime, timezone


def check_readiness(signal_state: dict = None) -> dict:
    """
    Check whether Paula has a usable input path for decision generation.

    Args:
        signal_state: Optional pre-fetched ATG signal dict.
                      If None, reports signal as unverified/missing.

    Returns:
        Structured readiness report.
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    blockers = []

    # --- signal source evaluation ---
    if signal_state is None:
        signal_source_status = "missing"
        blockers.append("no signal_state provided — call atg_signal.get_signal() first")
    else:
        sig_status = signal_state.get("signal_status", "missing")
        if sig_status == "fresh":
            signal_source_status = "available"
        elif sig_status == "stale":
            signal_source_status = "stale"
            reason = signal_state.get("reason", "signal is stale")
            blockers.append(f"signal stale: {reason}")
        else:
            signal_source_status = "missing"
            reason = signal_state.get("reason", "signal missing or unknown")
            blockers.append(f"signal unavailable: {reason}")

    # --- input availability ---
    input_available = signal_source_status == "available"
    if not input_available and signal_source_status != "missing":
        blockers.append("signal not fresh enough for decision generation")

    # --- symbol/context check ---
    if signal_state and not signal_state.get("symbol"):
        blockers.append("signal has no symbol context — Paula cannot route to asset")

    paula_ready = input_available and len(blockers) == 0

    return {
        "input_available": input_available,
        "signal_source_status": signal_source_status,
        "paula_ready": paula_ready,
        "blockers": blockers,
        "checked_at": checked_at,
    }
