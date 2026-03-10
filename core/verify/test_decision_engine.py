from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.decision_engine import classify_once


def test_nominal_classification() -> None:
    decision = classify_once(
        {"ok": True},
        {"ok": True},
        {"drift_count": 0},
    )

    assert decision == "nominal"


def test_operator_failure() -> None:
    decision = classify_once(
        {"ok": False},
        {"ok": True},
        {"drift_count": 0},
    )

    assert decision == "drift_detected"


def test_runtime_failure() -> None:
    decision = classify_once(
        {"ok": True},
        {"ok": False},
        {"drift_count": 0},
    )

    assert decision == "drift_detected"


def test_policy_drift() -> None:
    decision = classify_once(
        {"ok": True},
        {"ok": True},
        {"drift_count": 1},
    )

    assert decision == "drift_detected"


def test_missing_fields_returns_none() -> None:
    decision = classify_once(
        {"ok": True},
        {"ok": True},
        {},
    )

    assert decision is None


def test_malformed_input_returns_none() -> None:
    decision = classify_once(
        [],
        {"ok": True},
        {"drift_count": 0},
    )

    assert decision is None
