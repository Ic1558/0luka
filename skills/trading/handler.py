"""
trading/handler.py — Trading operations skill handler (read-only, stub data).
"""


_STUB_POSITIONS = [
    {"symbol": "BTC/USDT", "side": "long", "size": 0.1, "entry_price": 62000.0},
    {"symbol": "ETH/USDT", "side": "long", "size": 1.5, "entry_price": 3200.0},
]

_STUB_PNL = {
    "realized_pnl": 420.50,
    "unrealized_pnl": -35.20,
    "currency": "USDT",
}

_STUB_PORTFOLIO = {
    "total_value_usdt": 18500.0,
    "positions": len(_STUB_POSITIONS),
    "last_updated": "2026-03-18T00:00:00Z",
}


def execute(task: dict, context: dict) -> dict:
    """
    Execute a trading capability (read-only stub).

    Supported capabilities:
      - show_positions: list open positions
      - show_pnl: PnL summary
      - portfolio_summary: portfolio overview

    Returns:
      {"status": "success|error", "skill_id": "trading", "output": any, "trace_payload": dict}
    """
    capability = task.get("capability")

    trace_payload = {
        "skill_id": "trading",
        "capability": capability,
    }

    if capability == "show_positions":
        return {
            "status": "success",
            "skill_id": "trading",
            "output": _STUB_POSITIONS,
            "trace_payload": trace_payload,
        }

    elif capability == "show_pnl":
        return {
            "status": "success",
            "skill_id": "trading",
            "output": _STUB_PNL,
            "trace_payload": trace_payload,
        }

    elif capability == "portfolio_summary":
        return {
            "status": "success",
            "skill_id": "trading",
            "output": _STUB_PORTFOLIO,
            "trace_payload": trace_payload,
        }

    else:
        return {
            "status": "error",
            "skill_id": "trading",
            "output": None,
            "error": f"unknown capability: '{capability}'",
            "trace_payload": trace_payload,
        }
