"""AG-P11: Paula Controller — governed read-only trading brief for repos/option."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — OPTION_REPO is read-only source; all writes go to runtime state/
# ---------------------------------------------------------------------------
OPTION_REPO = Path("/Users/icmini/0luka/repos/option")

SAFE_READ_PATHS: dict[str, Path] = {
    "decision_history": OPTION_REPO / "artifacts/hq_decision_history.jsonl",
    "watchdog": OPTION_REPO / "artifacts/watchdog.log",
    "backtest_summary": OPTION_REPO / "artifacts/lab/backtests/BATCH_V1_3_20260311_234841/comparison_summary.json",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifacts_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "artifacts" / "paula"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data: dict) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read(path: Path) -> str | None:
    """Read a file only if it is inside OPTION_REPO. Raises on path escape."""
    resolved = path.resolve()
    if not str(resolved).startswith(str(OPTION_REPO.resolve())):
        raise ValueError(f"path_outside_repo: {resolved}")
    if not resolved.exists():
        return None
    return resolved.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 1: read raw state from repos/option (read-only, path-guarded)
# ---------------------------------------------------------------------------

def read_option_state() -> dict:
    """Read all safe source files. Never raises — errors captured per-file."""
    result: dict = {
        "decisions": [],
        "watchdog_lines": [],
        "backtest_variants": [],
        "source_files": [],
        "read_errors": {},
    }

    # decision_history.jsonl
    try:
        raw = _safe_read(SAFE_READ_PATHS["decision_history"])
        if raw:
            for line in raw.strip().splitlines():
                try:
                    result["decisions"].append(json.loads(line))
                except Exception:
                    pass
            result["source_files"].append("repos/option/artifacts/hq_decision_history.jsonl")
    except Exception as exc:
        result["read_errors"]["decision_history"] = str(exc)

    # watchdog.log
    try:
        raw = _safe_read(SAFE_READ_PATHS["watchdog"])
        if raw:
            result["watchdog_lines"] = raw.strip().splitlines()
            result["source_files"].append("repos/option/artifacts/watchdog.log")
    except Exception as exc:
        result["read_errors"]["watchdog"] = str(exc)

    # backtest_summary.json
    try:
        raw = _safe_read(SAFE_READ_PATHS["backtest_summary"])
        if raw:
            parsed = json.loads(raw)
            result["backtest_variants"] = parsed if isinstance(parsed, list) else [parsed]
            result["source_files"].append(
                "repos/option/artifacts/lab/backtests/BATCH_V1_3_20260311_234841/comparison_summary.json"
            )
    except Exception as exc:
        result["read_errors"]["backtest_summary"] = str(exc)

    return result


# ---------------------------------------------------------------------------
# Phase 2: normalize into trading summary
# ---------------------------------------------------------------------------

def summarize_option_state(raw: dict) -> dict:
    """Pure normalization — no I/O, no writes."""
    summary: dict = {
        "repo_health": {},
        "strategy_mode": {},
        "current_risk_posture": {},
        "next_action_recommendation": {},
        "open_unknowns": [],
    }

    # --- repo_health: parse last watchdog line ---
    watchdog_lines = raw.get("watchdog_lines", [])
    if watchdog_lines:
        last_line = watchdog_lines[-1]
        summary["repo_health"] = {
            "last_watchdog_line": last_line,
            "line_count": len(watchdog_lines),
            "status": "healthy" if "healthy" in last_line.lower() else "unknown",
        }
    else:
        summary["repo_health"] = {"status": "no_data"}
        summary["open_unknowns"].append("watchdog.log missing or empty")

    # --- strategy_mode: last 5 decisions ---
    decisions = raw.get("decisions", [])
    last5 = decisions[-5:] if len(decisions) >= 5 else decisions
    if last5:
        latest = last5[-1]
        summary["strategy_mode"] = {
            "last_recommendation": latest.get("recommendation"),
            "last_actionable_bias": latest.get("actionable_bias"),
            "last_global_score": latest.get("global_score"),
            "last_timestamp": latest.get("timestamp"),
            "last_symbol": (latest.get("signal") or {}).get("symbol"),
            "recent_count": len(last5),
        }
    else:
        summary["strategy_mode"] = {"status": "no_decisions"}
        summary["open_unknowns"].append("decision_history missing or empty")

    # --- current_risk_posture: levels + backtest false-BEAR count ---
    levels = {}
    if decisions:
        latest_with_levels = next(
            (d for d in reversed(decisions) if d.get("levels")), None
        )
        if latest_with_levels:
            levels = latest_with_levels.get("levels", {})

    best_variant = None
    false_bear_count = None
    variants = raw.get("backtest_variants", [])
    if variants:
        try:
            best_variant = max(variants, key=lambda v: float(v.get("expectancy", 0) or 0))
            false_bear_count = best_variant.get("false_bear_count") or best_variant.get("false_BEAR_count")
        except Exception:
            pass

    summary["current_risk_posture"] = {
        "levels": levels,
        "best_backtest_variant": best_variant.get("variant") if best_variant else None,
        "best_expectancy": best_variant.get("expectancy") if best_variant else None,
        "false_bear_count": false_bear_count,
    }
    if not levels:
        summary["open_unknowns"].append("no TP/SL levels in recent decisions")
    if not best_variant:
        summary["open_unknowns"].append("backtest_summary missing or unparseable")

    # --- next_action_recommendation: from latest decision ---
    if decisions:
        latest = decisions[-1]
        summary["next_action_recommendation"] = {
            "recommendation": latest.get("recommendation"),
            "actionable_bias": latest.get("actionable_bias"),
            "global_score": latest.get("global_score"),
            "timestamp": latest.get("timestamp"),
            "levels": latest.get("levels", {}),
        }
    else:
        summary["next_action_recommendation"] = {"status": "no_data"}

    return summary


# ---------------------------------------------------------------------------
# Phase 3: build governed prompt
# ---------------------------------------------------------------------------

def build_brief_prompt(summary: dict) -> str:
    mode = summary.get("strategy_mode", {})
    posture = summary.get("current_risk_posture", {})
    action = summary.get("next_action_recommendation", {})
    health = summary.get("repo_health", {})

    return (
        f"Paula trading brief for repos/option. "
        f"Repo health: {health.get('status', 'unknown')}. "
        f"Last recommendation: {action.get('recommendation')} "
        f"(bias={action.get('actionable_bias')}, score={action.get('global_score')}). "
        f"Levels: {action.get('levels')}. "
        f"Best backtest: {posture.get('best_backtest_variant')} "
        f"(expectancy={posture.get('best_expectancy')}, false_bear={posture.get('false_bear_count')}). "
        f"Produce a 3-line professional read-only trading brief. No order execution. No advice."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_paula_brief(operator_id: str = "boss", provider: str = "claude") -> dict:
    """Governed read-only Paula brief. Returns full evidence record."""
    from runtime.operator_task import _check_approval
    from runtime.governed_inference import route_inference

    brief_id = f"paula_{uuid.uuid4().hex[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    ts = _now()

    # --- approval gate (fail-closed) ---
    approved, approval_reason = _check_approval()
    if not approved:
        record: dict = {
            "brief_id": brief_id,
            "task_id": "paula_brief",
            "operator_id": operator_id,
            "provider": provider,
            "ts": ts,
            "governed": True,
            "approved": False,
            "block_reason": approval_reason,
            "source_files": [],
            "summary": {},
            "inference_id": None,
            "brief": None,
            "status": "blocked",
        }
        sd = _state_dir()
        _atomic_write(sd / "paula_brief_latest.json", record)
        _append_jsonl(sd / "paula_brief_log.jsonl", record)
        return record

    # --- read + summarize ---
    raw = read_option_state()
    summary = summarize_option_state(raw)
    prompt = build_brief_prompt(summary)

    # --- governed inference ---
    inference_result = route_inference(prompt, provider, operator_id)
    brief_text: str | None = inference_result.get("response")

    record = {
        "brief_id": brief_id,
        "task_id": "paula_brief",
        "operator_id": operator_id,
        "provider": provider,
        "ts": ts,
        "governed": True,
        "approved": True,
        "block_reason": None,
        "source_files": raw.get("source_files", []),
        "summary": summary,
        "inference_id": inference_result.get("inference_id"),
        "brief": brief_text,
        "status": "executed",
    }

    # --- write evidence ---
    sd = _state_dir()
    _atomic_write(sd / "paula_brief_latest.json", record)
    _append_jsonl(sd / "paula_brief_log.jsonl", record)

    ad = _artifacts_dir()
    _atomic_write(ad / f"{brief_id}.json", record)

    return record
