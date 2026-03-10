from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.ops.decision_engine import classify_once


def _normalize_input(payload: Any) -> dict[str, Any] | None:
    return payload if isinstance(payload, dict) else None


def persist_decision(
    root_path: str | Path,
    operator_status: Any,
    runtime_status: Any,
    policy_drift: Any,
    ts_utc: str,
) -> dict[str, Any]:
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)

    operator = _normalize_input(operator_status)
    runtime = _normalize_input(runtime_status)
    drift = _normalize_input(policy_drift)

    classification = classify_once(
        operator_status=operator,
        runtime_status=runtime,
        policy_drift=drift,
    )

    payload = {
        "ts_utc": ts_utc,
        "classification": classification,
        "inputs": {
            "operator_status": operator,
            "runtime_status": runtime,
            "policy_drift": drift,
        },
    }

    log_path = root / "decision_log.jsonl"
    latest_path = root / "decision_latest.json"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    latest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload
