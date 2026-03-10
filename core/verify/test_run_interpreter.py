from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.run_interpreter import interpret_run


def test_interpret_run_complete_signal() -> None:
    result = interpret_run(
        {"run_id": "run_123"},
        ["proof_pack:run_123", "ledger_proof_export:run_123"],
    )

    assert result == {
        "run_id": "run_123",
        "artifact_count": 2,
        "expected_artifacts": [
            "proof_pack:run_123",
            "ledger_proof_export:run_123",
        ],
        "missing_artifacts": [],
        "signal": "COMPLETE",
    }


def test_interpret_run_partial_signal() -> None:
    result = interpret_run(
        {"run_id": "run_123"},
        ["proof_pack:run_123"],
    )

    assert result == {
        "run_id": "run_123",
        "artifact_count": 1,
        "expected_artifacts": [
            "proof_pack:run_123",
            "ledger_proof_export:run_123",
        ],
        "missing_artifacts": ["ledger_proof_export:run_123"],
        "signal": "PARTIAL",
    }


def test_interpret_run_missing_proof_signal() -> None:
    result = interpret_run(
        {"run_id": "run_123"},
        [],
    )

    assert result == {
        "run_id": "run_123",
        "artifact_count": 0,
        "expected_artifacts": [
            "proof_pack:run_123",
            "ledger_proof_export:run_123",
        ],
        "missing_artifacts": [
            "proof_pack:run_123",
            "ledger_proof_export:run_123",
        ],
        "signal": "MISSING_PROOF",
    }


def test_interpret_run_inconsistent_signal() -> None:
    result = interpret_run(
        {"run_id": "run_123"},
        ["proof_pack:run_123", "proof_pack:other_run"],
    )

    assert result == {
        "run_id": "run_123",
        "artifact_count": 1,
        "expected_artifacts": [
            "proof_pack:run_123",
            "ledger_proof_export:run_123",
        ],
        "missing_artifacts": ["ledger_proof_export:run_123"],
        "signal": "INCONSISTENT",
    }
