from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import system_model_summary


def test_summary_derivation_basic() -> None:
    summary = system_model_summary.derive_summary(
        {
            "ts_utc": "2026-03-11T00:00:00Z",
            "kernel_components": ["dispatcher", "worker", "bridge", "queue", "runtime"],
            "observability_surfaces": ["activity", "proofs", "runs", "signals", "preview", "memory", "mirror"],
            "decision_memory_present": True,
            "autonomy_enabled": False,
        }
    )

    assert summary == {
        "ts_utc": "2026-03-11T00:00:00Z",
        "kernel_components": 5,
        "observability_surfaces": 7,
        "decision_layer_present": True,
        "autonomy_layer_present": False,
    }


def test_summary_no_side_effects(monkeypatch) -> None:
    def fail_open(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected I/O")

    monkeypatch.setattr(builtins, "open", fail_open)

    summary = system_model_summary.derive_summary({"decision_memory_present": False, "autonomy_enabled": False})

    assert summary["decision_layer_present"] is False
    assert summary["autonomy_layer_present"] is False


def test_summary_write_atomic(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "system_model.json").write_text(
        json.dumps(
            {
                "ts_utc": "2026-03-11T00:00:00Z",
                "kernel_components": ["dispatcher"],
                "observability_surfaces": ["runs", "signals"],
                "decision_memory_present": True,
                "autonomy_enabled": False,
            }
        ),
        encoding="utf-8",
    )

    system_model_summary.generate_summary(tmp_path)

    summary_path = state_dir / "system_model_summary.json"
    assert summary_path.exists()
    assert not (state_dir / "system_model_summary.json.tmp").exists()
    assert json.loads(summary_path.read_text(encoding="utf-8")) == {
        "ts_utc": "2026-03-11T00:00:00Z",
        "kernel_components": 1,
        "observability_surfaces": 2,
        "decision_layer_present": True,
        "autonomy_layer_present": False,
    }
