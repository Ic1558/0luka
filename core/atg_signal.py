"""
atg_signal.py — ATG signal path: structured signal status with explicit freshness.

Invariants:
  - No live order placement
  - Stale/missing signals are explicit, never hidden
  - Structured contract always returned

Output contract:
  {
    "signal_status": "fresh" | "stale" | "missing",
    "freshness": "current" | "degraded" | "expired" | "unknown",
    "symbol": str | None,
    "direction": "long" | "short" | "neutral" | None,
    "confidence": float | None,
    "reason": str,
    "generated_at": str,
  }
"""

from datetime import datetime, timezone


# Known symbols available via stub trading data
_KNOWN_SYMBOLS = ["BTC/USDT", "ETH/USDT"]

# ATG signal store — in-memory for this phase (no live feed yet)
_signal_store: dict = {}


def emit_signal(symbol: str, direction: str, confidence: float = 0.7,
                freshness: str = "current") -> dict:
    """
    Emit (record) an ATG signal for a symbol.

    Args:
        symbol: Asset symbol (e.g. "BTC/USDT").
        direction: "long" | "short" | "neutral"
        confidence: 0.0–1.0
        freshness: "current" | "degraded" | "expired"

    Returns:
        Structured signal record.
    """
    if direction not in ("long", "short", "neutral"):
        direction = "neutral"
    confidence = max(0.0, min(1.0, float(confidence)))
    generated_at = datetime.now(timezone.utc).isoformat()

    signal = {
        "signal_status": "fresh" if freshness == "current" else "stale",
        "freshness": freshness,
        "symbol": symbol,
        "direction": direction,
        "confidence": confidence,
        "reason": f"signal emitted for {symbol}",
        "generated_at": generated_at,
    }
    _signal_store[symbol] = signal
    return dict(signal)  # return copy — callers must not be mutated by later mark_stale


def get_signal(symbol: str = None) -> dict:
    """
    Retrieve current ATG signal for a specific symbol.

    Args:
        symbol: Asset symbol (e.g. "BTC/USDT").

    Returns:
        Structured signal dict. signal_status="missing" if symbol is None
        or no signal is found for the requested symbol.
    """
    generated_at = datetime.now(timezone.utc).isoformat()

    if symbol:
        sig = _signal_store.get(symbol)
        if sig:
            return dict(sig)  # return copy

    return {
        "signal_status": "missing",
        "freshness": "unknown",
        "symbol": symbol,
        "direction": None,
        "confidence": None,
        "reason": f"no ATG signal recorded for {symbol}" if symbol else "ambiguous query: symbol is None",
        "generated_at": generated_at,
    }


def mark_stale(symbol: str, reason: str = "expired by operator") -> dict:
    """
    Mark an existing signal as stale.

    Args:
        symbol: Asset symbol to mark stale.
        reason: Human-readable reason.

    Returns:
        Updated signal dict, or missing dict if not found.
    """
    if symbol not in _signal_store:
        return get_signal(symbol)

    _signal_store[symbol]["signal_status"] = "stale"
    _signal_store[symbol]["freshness"] = "expired"
    _signal_store[symbol]["reason"] = reason
    return dict(_signal_store[symbol])  # return copy
