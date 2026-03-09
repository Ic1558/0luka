from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import recovery_guardrails, remediation_queue, self_healing_worker


def _dt(iso_z: str) -> datetime:
    return datetime.fromisoformat(iso_z.replace("Z", "+00:00")).astimezone(timezone.utc)


def _queue_item(runtime_root: Path, item_id: str) -> dict[str, object]:
    payload = remediation_queue.list_queue(runtime_root=runtime_root)
    for row in payload["items"]:
        if row.get("id") == item_id:
            return row
    raise AssertionError("queue item missing")


def _history_rows(runtime_root: Path) -> list[dict[str, object]]:
    path = runtime_root / "state" / "remediation_history.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_rate_limit_triggers_after_threshold(tmp_path) -> None:
    now = _dt("2026-03-08T10:00:00Z")
    for offset in (0, 10, 20):
        recovery_guardrails.register_result(
            lane="worker_recovery",
            action="restart_worker",
            result="blocked",
            runtime_root=tmp_path,
            now=now + timedelta(seconds=offset),
        )

    verdict = recovery_guardrails.evaluate(
        lane="worker_recovery",
        action="restart_worker",
        item_attempts=0,
        runtime_root=tmp_path,
        now=now + timedelta(seconds=30),
    )

    assert verdict["allowed"] is False
    assert verdict["decision"] == "rate_limited"


def test_retry_limit_triggers_after_max_attempts(tmp_path) -> None:
    verdict = recovery_guardrails.evaluate(
        lane="worker_recovery",
        action="restart_worker",
        item_attempts=5,
        runtime_root=tmp_path,
        now=_dt("2026-03-08T10:00:00Z"),
    )

    assert verdict["allowed"] is False
    assert verdict["decision"] == "retry_limit_exceeded"
    assert verdict["queue_state"] == "failed"


def test_backoff_values_correct_for_attempts() -> None:
    assert recovery_guardrails.backoff_seconds(1) == 2
    assert recovery_guardrails.backoff_seconds(2) == 5
    assert recovery_guardrails.backoff_seconds(3) == 10
    assert recovery_guardrails.backoff_seconds(4) == 30
    assert recovery_guardrails.backoff_seconds(9) == 30


def test_cooldown_blocks_repeated_execution(tmp_path) -> None:
    now = _dt("2026-03-08T10:00:00Z")
    recovery_guardrails.register_result(
        lane="worker_recovery",
        action="restart_worker",
        result="success",
        runtime_root=tmp_path,
        now=now,
    )

    verdict = recovery_guardrails.evaluate(
        lane="worker_recovery",
        action="restart_worker",
        item_attempts=0,
        runtime_root=tmp_path,
        now=now + timedelta(seconds=20),
    )

    assert verdict["allowed"] is False
    assert verdict["decision"] == "cooldown_active"


def test_loop_protection_halts_repeated_failures(tmp_path) -> None:
    now = _dt("2026-03-08T10:00:00Z")
    for idx in range(3):
        recovery_guardrails.register_result(
            lane="worker_recovery",
            action="restart_worker",
            result="failed",
            runtime_root=tmp_path,
            now=now + timedelta(seconds=idx),
        )

    verdict = recovery_guardrails.evaluate(
        lane="worker_recovery",
        action="restart_worker",
        item_attempts=0,
        runtime_root=tmp_path,
        now=now + timedelta(seconds=5),
    )

    assert verdict["allowed"] is False
    assert verdict["decision"] == "loop_protection_triggered"


def test_healthy_execution_path_still_succeeds(tmp_path, monkeypatch) -> None:
    item = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )["item"]
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (True, "approved_and_available"))
    monkeypatch.setattr(self_healing_worker, "_execute_action", lambda action: (True, "ok"))

    result = self_healing_worker.process_once(runtime_root=tmp_path)

    assert result["result"] == "success"
    queue_item = _queue_item(tmp_path, str(item["id"]))
    assert queue_item["state"] == "success"


def test_self_healing_worker_respects_guardrail_denial(tmp_path, monkeypatch) -> None:
    item = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )["item"]
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (True, "approved_and_available"))
    monkeypatch.setattr(
        recovery_guardrails,
        "evaluate",
        lambda **kwargs: {"allowed": False, "decision": "rate_limited", "queue_state": "blocked"},
    )

    result = self_healing_worker.process_once(runtime_root=tmp_path)

    assert result["result"] == "blocked"
    queue_item = _queue_item(tmp_path, str(item["id"]))
    assert queue_item["state"] == "blocked"
    rows = _history_rows(tmp_path)
    assert rows[-1]["decision"] == "rate_limited"


def test_no_mutation_outside_queue_guardrail_history_state(tmp_path, monkeypatch) -> None:
    remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (True, "approved_and_available"))
    monkeypatch.setattr(self_healing_worker, "_execute_action", lambda action: (True, "ok"))

    self_healing_worker.process_once(runtime_root=tmp_path)

    assert (tmp_path / "state" / "remediation_queue.json").exists()
    assert (tmp_path / "state" / "recovery_guardrails.json").exists()
    assert (tmp_path / "state" / "remediation_history.jsonl").exists()

    created = {path.name for path in (tmp_path / "state").iterdir()}
    assert created.issubset({"remediation_queue.json", "recovery_guardrails.json", "remediation_history.jsonl"})
