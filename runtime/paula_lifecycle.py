"""AG-P14: Paula paper trade lifecycle — ack, evaluate, close, PnL."""
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


# ── Path helpers (mirror paula_controller pattern) ─────────────────────────────
def _runtime_root() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    return Path(rt)


def _state_dir() -> Path:
    d = _runtime_root() / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifacts_dir() -> Path:
    d = _runtime_root() / "artifacts" / "paula"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Transition gate ────────────────────────────────────────────────────────────
VALID_TRANSITIONS: dict[str, set[str]] = {
    "recorded":     {"acknowledged"},
    "acknowledged": {"active", "closed_tp", "closed_sl", "closed_manual", "expired"},
    "active":       {"closed_tp", "closed_sl", "closed_manual", "expired"},
}


def _assert_transition(current: str, target: str) -> None:
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(
            f"Invalid transition {current!r} → {target!r}. Allowed: {allowed}"
        )


# ── Storage helpers ────────────────────────────────────────────────────────────
def _load_trade(paper_trade_id: str) -> dict:
    p = _artifacts_dir() / f"{paper_trade_id}.json"
    if not p.exists():
        raise FileNotFoundError(f"Trade not found: {paper_trade_id}")
    return json.loads(p.read_text())


def _save_trade(trade: dict) -> None:
    pid = trade["paper_trade_id"]
    p = _artifacts_dir() / f"{pid}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(trade, indent=2))
    tmp.replace(p)
    # Update latest pointer if this trade IS the current latest
    latest_p = _state_dir() / "paula_paper_latest.json"
    try:
        latest = json.loads(latest_p.read_text()) if latest_p.exists() else {}
        if latest.get("paper_trade_id") == pid:
            tmp2 = latest_p.with_suffix(".tmp")
            tmp2.write_text(json.dumps(trade, indent=2))
            tmp2.replace(latest_p)
    except Exception:
        pass


def _append_event(event: dict) -> None:
    p = _state_dir() / "paula_paper_log.jsonl"
    with open(p, "a") as f:
        f.write(json.dumps(event) + "\n")


# ── Approval gate (same pattern as paula_controller) ──────────────────────────
def _check_approval() -> tuple[bool, str]:
    try:
        from tools.ops.approval_state import load_approval_state
        state = load_approval_state()
        lane = state["lanes"].get("task_execution", {})
        if lane.get("approved_effective"):
            return True, "approved"
        reason = "approval_expired" if lane.get("expired") else "approval_missing"
        return False, reason
    except Exception as exc:
        return False, f"approval_check_error:{exc}"


# ── PnL computation ────────────────────────────────────────────────────────────
def compute_pnl(
    trade: dict,
    exit_price: float,
    hit_tp: Optional[str] = None,
    hit_sl: bool = False,
) -> dict:
    entry = trade.get("entry_hint")
    sl = trade.get("sl")
    direction = trade.get("direction", "LONG")
    rr = None
    if entry and sl and abs(entry - sl) > 0:
        risk = abs(entry - sl)
        if direction == "LONG":
            rr = round((exit_price - entry) / risk, 3)
        else:
            rr = round((entry - exit_price) / risk, 3)
    result = "win" if hit_tp else ("loss" if hit_sl else "neutral")
    return {"result": result, "rr": rr, "hit_tp": hit_tp, "hit_sl": hit_sl}


# ── Core lifecycle functions ───────────────────────────────────────────────────
def ack_paper_trade(paper_trade_id: str, operator_id: str) -> dict:
    """Transition recorded → acknowledged. Approval-gated."""
    approved, reason = _check_approval()
    if not approved:
        return {
            "status": "blocked",
            "block_reason": reason,
            "paper_trade_id": paper_trade_id,
        }
    trade = _load_trade(paper_trade_id)
    _assert_transition(trade["status"], "acknowledged")
    trade["status"] = "acknowledged"
    trade["ack_operator_id"] = operator_id
    trade["ack_ts"] = _now()
    _save_trade(trade)
    event = {
        "event": "ack",
        "paper_trade_id": paper_trade_id,
        "status": "acknowledged",
        "pnl": None,
        "ts": trade["ack_ts"],
        "operator_id": operator_id,
        "governed": True,
    }
    _append_event(event)
    return {
        "status": "acknowledged",
        "paper_trade_id": paper_trade_id,
        "operator_id": operator_id,
    }


def close_paper_trade(
    trade: dict,
    new_status: str,
    exit_price: float,
    operator_id: Optional[str] = None,
    hit_tp: Optional[str] = None,
) -> dict:
    """Close a trade to any terminal status. Mutates and persists trade."""
    _assert_transition(trade["status"], new_status)
    hit_sl = new_status == "closed_sl"
    pnl = compute_pnl(trade, exit_price, hit_tp=hit_tp, hit_sl=hit_sl)
    ts = _now()
    trade.update(
        {
            "status": new_status,
            "closed_at": ts,
            "close_reason": (
                new_status.replace("closed_", "")
                if new_status.startswith("closed_")
                else new_status
            ),
            "exit_price": exit_price,
            "pnl": pnl,
        }
    )
    _save_trade(trade)
    event = {
        "event": "close",
        "paper_trade_id": trade["paper_trade_id"],
        "status": new_status,
        "pnl": pnl,
        "ts": ts,
        "operator_id": operator_id,
        "governed": True,
    }
    _append_event(event)
    return trade


def evaluate_paper_trade(
    paper_trade_id: str,
    latest_price: float,
    operator_id: str = "boss",
) -> dict:
    """Evaluate a trade against latest_price. Closes if TP/SL/expiry hit.
    Approval-gated when closing. Returns updated trade dict or status info."""
    trade = _load_trade(paper_trade_id)
    if trade["status"] not in ("acknowledged", "active"):
        return {
            "status": trade["status"],
            "changed": False,
            "paper_trade_id": paper_trade_id,
        }
    direction = trade["direction"]
    sl = trade.get("sl")
    tp_levels = trade.get("tp_levels") or {}
    ts = (
        datetime.fromisoformat(trade["ts"])
        if "ts" in trade
        else datetime.now(timezone.utc)
    )

    # Determine outcome
    close_kwargs: Optional[dict] = None
    if sl:
        sl_hit = (direction == "LONG" and latest_price <= sl) or (
            direction == "SHORT" and latest_price >= sl
        )
        if sl_hit:
            close_kwargs = {"new_status": "closed_sl", "exit_price": sl}
    if close_kwargs is None:
        for tp_name in ("TP1", "TP2", "TP3"):
            tp_val = tp_levels.get(tp_name)
            if tp_val is None:
                continue
            tp_hit = (direction == "LONG" and latest_price >= tp_val) or (
                direction == "SHORT" and latest_price <= tp_val
            )
            if tp_hit:
                close_kwargs = {
                    "new_status": "closed_tp",
                    "exit_price": tp_val,
                    "hit_tp": tp_name,
                }
                break
    if close_kwargs is None:
        if datetime.now(timezone.utc) - ts > timedelta(hours=24):
            close_kwargs = {"new_status": "expired", "exit_price": latest_price}

    if close_kwargs is None:
        # Mark active if it was still acknowledged
        if trade["status"] == "acknowledged":
            trade["status"] = "active"
            _save_trade(trade)
        return {
            "status": trade["status"],
            "changed": False,
            "paper_trade_id": paper_trade_id,
        }

    # Gate close on approval
    approved, reason = _check_approval()
    if not approved:
        return {
            "status": "blocked",
            "block_reason": reason,
            "paper_trade_id": paper_trade_id,
        }
    return close_paper_trade(trade, operator_id=operator_id, **close_kwargs)
