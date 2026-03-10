from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.decision_persist import persist_decision


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_nominal_decision_persists_to_both_files(tmp_path: Path) -> None:
    payload = persist_decision(
        tmp_path,
        {"ok": True, "overall_status": "HEALTHY"},
        {"ok": True, "overall_status": "HEALTHY"},
        {"ok": True, "drift_count": 0},
        "2026-03-11T00:00:00Z",
    )

    assert payload["classification"] == "nominal"
    assert _read_json(tmp_path / "decision_latest.json")["classification"] == "nominal"
    assert _read_jsonl(tmp_path / "decision_log.jsonl")[0]["classification"] == "nominal"


def test_drift_detected_persists_to_both_files(tmp_path: Path) -> None:
    payload = persist_decision(
        tmp_path,
        {"ok": False},
        {"ok": True},
        {"ok": True, "drift_count": 0},
        "2026-03-11T00:05:00Z",
    )

    assert payload["classification"] == "drift_detected"
    assert _read_json(tmp_path / "decision_latest.json")["classification"] == "drift_detected"
    assert _read_jsonl(tmp_path / "decision_log.jsonl")[0]["classification"] == "drift_detected"


def test_null_classification_persists_correctly(tmp_path: Path) -> None:
    payload = persist_decision(
        tmp_path,
        {"ok": True},
        {"ok": True},
        {"unexpected": 1},
        "2026-03-11T00:10:00Z",
    )

    assert payload["classification"] is None
    assert _read_json(tmp_path / "decision_latest.json")["classification"] is None
    assert _read_jsonl(tmp_path / "decision_log.jsonl")[0]["classification"] is None


def test_log_appends_while_latest_overwrites(tmp_path: Path) -> None:
    persist_decision(
        tmp_path,
        {"ok": True},
        {"ok": True},
        {"ok": True, "drift_count": 0},
        "2026-03-11T00:15:00Z",
    )
    persist_decision(
        tmp_path,
        {"ok": False},
        {"ok": True},
        {"ok": True, "drift_count": 0},
        "2026-03-11T00:16:00Z",
    )

    rows = _read_jsonl(tmp_path / "decision_log.jsonl")
    latest = _read_json(tmp_path / "decision_latest.json")
    assert len(rows) == 2
    assert rows[0]["classification"] == "nominal"
    assert rows[1]["classification"] == "drift_detected"
    assert latest["ts_utc"] == "2026-03-11T00:16:00Z"
    assert latest["classification"] == "drift_detected"


def test_only_expected_files_are_created(tmp_path: Path) -> None:
    persist_decision(
        tmp_path,
        {"ok": True},
        {"ok": True},
        {"ok": True, "drift_count": 0},
        "2026-03-11T00:20:00Z",
    )

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "decision_latest.json",
        "decision_log.jsonl",
    ]


def test_persisted_json_shape_is_correct(tmp_path: Path) -> None:
    payload = persist_decision(
        tmp_path,
        {"ok": True},
        {"ok": True},
        {"ok": True, "drift_count": 0},
        "2026-03-11T00:25:00Z",
    )

    assert payload == {
        "ts_utc": "2026-03-11T00:25:00Z",
        "classification": "nominal",
        "inputs": {
            "operator_status": {"ok": True},
            "runtime_status": {"ok": True},
            "policy_drift": {"ok": True, "drift_count": 0},
        },
    }
