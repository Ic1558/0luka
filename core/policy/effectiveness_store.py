"""AG-29: Policy effectiveness store.

State files (under LUKA_RUNTIME_ROOT/state/):
  policy_effectiveness.json        latest verdict per policy_id (dict)
  policy_verification_log.jsonl    append-only history of verifications

All writes are atomic (temp + os.replace).

Also exposes evaluate_policy_effectiveness() — a direct-path variant that
reads activation_log and learning_observations from state_dir without
depending on higher-level module imports (robust for isolated test/CLI use).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


_EFFECTIVENESS_NAME = "policy_effectiveness.json"
_VERIFICATION_LOG_NAME = "policy_verification_log.jsonl"


def _state_dir() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


# ---------------------------------------------------------------------------
# Direct-path evaluator (no module-level imports, robust for isolated use)
# ---------------------------------------------------------------------------

def evaluate_policy_effectiveness(policy_id: str) -> dict[str, Any]:
    """Compare observations before/after policy activation.

    Reads directly from state_dir JSONL files.
    Returns effectiveness verdict dict.

    Activation log field: "ts" (ISO UTC string).
    Observation fields: "timestamp" (ISO UTC), "execution_result" (SUCCESS/FAILED/PARTIAL).
    """
    state = _state_dir()
    activation_log = _load_jsonl(state / "policy_activation_log.jsonl")
    observations = _load_jsonl(state / "learning_observations.jsonl")

    # Find the most recent ACTIVATED event for this policy
    # Activation log uses "ts", not "timestamp"
    activation = next(
        (a for a in reversed(activation_log)
         if a.get("policy_id") == policy_id and a.get("status") == "ACTIVATED"),
        None,
    )
    if not activation:
        return {"policy_id": policy_id, "verdict": "INCONCLUSIVE", "reason": "not_in_activation_log"}

    activated_at = str(activation.get("ts") or activation.get("timestamp") or "")
    if not activated_at:
        return {"policy_id": policy_id, "verdict": "INCONCLUSIVE", "reason": "missing_activation_ts"}

    before = [o for o in observations if str(o.get("timestamp") or "") < activated_at]
    after = [o for o in observations if str(o.get("timestamp") or "") >= activated_at]

    if not after:
        return {
            "policy_id": policy_id,
            "verdict": "INCONCLUSIVE",
            "reason": "no_post_promotion_observations",
            "before_count": len(before),
            "after_count": 0,
        }

    before_errors = sum(
        1 for o in before
        if str(o.get("execution_result") or o.get("outcome") or "").upper()
        in ("FAILED", "PARTIAL", "FAILURE")
    )
    after_errors = sum(
        1 for o in after
        if str(o.get("execution_result") or o.get("outcome") or "").upper()
        in ("FAILED", "PARTIAL", "FAILURE")
    )

    if after_errors < before_errors:
        verdict = "KEEP"
    elif after_errors > before_errors:
        verdict = "ROLLBACK_RECOMMENDED"
    else:
        verdict = "REVIEW"

    return {
        "policy_id": policy_id,
        "verdict": verdict,
        "before_failures": before_errors,
        "after_failures": after_errors,
        "before_count": len(before),
        "after_count": len(after),
        "activated_at": activated_at,
    }


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_effectiveness(record: dict[str, Any]) -> None:
    """Upsert one policy's effectiveness record into policy_effectiveness.json."""
    p = _state_dir() / _EFFECTIVENESS_NAME
    try:
        current: dict[str, Any] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (json.JSONDecodeError, OSError):
        current = {}
    policy_id = str(record.get("policy_id") or "")
    if policy_id:
        current[policy_id] = dict(record, updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def append_verification_log(record: dict[str, Any]) -> None:
    """Append one verification record to policy_verification_log.jsonl."""
    entry = dict(record)
    if not entry.get("ts"):
        entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log_path = _state_dir() / _VERIFICATION_LOG_NAME
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    tmp = log_path.with_suffix(".tmp")
    tmp.write_text(existing + json.dumps(entry) + "\n", encoding="utf-8")
    os.replace(tmp, log_path)


def get_effectiveness(policy_id: str) -> dict[str, Any] | None:
    """Return the latest effectiveness record for a policy, or None."""
    p = _state_dir() / _EFFECTIVENESS_NAME
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get(policy_id)
    except (json.JSONDecodeError, OSError):
        return None


def list_effectiveness() -> list[dict[str, Any]]:
    """Return all effectiveness records as a list."""
    p = _state_dir() / _EFFECTIVENESS_NAME
    if not p.exists():
        return []
    try:
        return list(json.loads(p.read_text(encoding="utf-8")).values())
    except (json.JSONDecodeError, OSError):
        return []


def list_verification_log(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent verification log entries."""
    log_path = _state_dir() / _VERIFICATION_LOG_NAME
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records[-limit:]


# ---------------------------------------------------------------------------
# Run verification + persist (orchestration helper)
# ---------------------------------------------------------------------------

def run_and_persist(policy_id: str) -> dict[str, Any]:
    """Evaluate effectiveness, persist to store, append to verification log.

    Returns the effectiveness record.  Never raises.
    """
    try:
        record = evaluate_policy_effectiveness(policy_id)
    except Exception as exc:
        record = {
            "policy_id": policy_id,
            "verdict": "INCONCLUSIVE",
            "reason": f"evaluation_error:{exc}",
        }
    try:
        save_effectiveness(record)
        append_verification_log(record)
    except Exception:
        pass  # fail-open: persist errors don't block callers
    return record
