from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.decision_engine import classify_once


def test_nominal_returns_nominal_decision() -> None:
    decision = classify_once(
        operator_status={"ok": True, "overall_status": "HEALTHY"},
        runtime_status={"ok": True, "overall_status": "HEALTHY"},
        policy_drift={"ok": True, "drift_count": 0},
        ts_utc="2026-03-10T12:00:00Z",
    )

    assert decision == {
        "ts_utc": "2026-03-10T12:00:00Z",
        "type": "nominal",
        "source": ["operator_status", "runtime_status", "policy_drift"],
        "evidence": {
            "operator_status": {"ok": True, "overall_status": "HEALTHY"},
            "runtime_status": {"ok": True, "overall_status": "HEALTHY"},
            "policy_drift": {"ok": True, "drift_count": 0},
        },
    }


def test_drift_detected_returns_drift_decision() -> None:
    decision = classify_once(
        operator_status={"ok": True, "overall_status": "HEALTHY"},
        runtime_status={"ok": True, "overall_status": "HEALTHY"},
        policy_drift={"ok": False, "drift_count": 1},
        ts_utc="2026-03-10T12:05:00Z",
    )

    assert decision == {
        "ts_utc": "2026-03-10T12:05:00Z",
        "type": "drift_detected",
        "source": ["policy_drift"],
        "evidence": {
            "policy_drift": {"ok": False, "drift_count": 1},
        },
    }
