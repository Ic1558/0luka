from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import remediation_queue, self_healing_worker


def _load_queue_item(runtime_root: Path, item_id: str) -> dict[str, object]:
    payload = remediation_queue.list_queue(runtime_root=runtime_root)
    for row in payload["items"]:
        if row.get("id") == item_id:
            return row
    raise AssertionError("queue item not found")


def _load_history_rows(runtime_root: Path) -> list[dict[str, object]]:
    path = runtime_root / "state" / "remediation_history.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_queue_item_executed_successfully(tmp_path, monkeypatch) -> None:
    item = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )["item"]
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (True, "approved_and_available"))
    monkeypatch.setattr(self_healing_worker, "_execute_action", lambda action: (True, "ok"))

    payload = self_healing_worker.process_once(runtime_root=tmp_path)

    assert payload["ok"] is True
    assert payload["result"] == "success"
    queue_item = _load_queue_item(tmp_path, str(item["id"]))
    assert queue_item["state"] == "success"


def test_policy_block_respected(tmp_path, monkeypatch) -> None:
    item = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )["item"]
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (False, "policy_denied"))

    payload = self_healing_worker.process_once(runtime_root=tmp_path)

    assert payload["result"] == "blocked"
    queue_item = _load_queue_item(tmp_path, str(item["id"]))
    assert queue_item["state"] == "blocked"


def test_approval_missing_blocked(tmp_path, monkeypatch) -> None:
    item = remediation_queue.enqueue_item(
        lane="api_recovery",
        action="restart_api",
        runtime_root=tmp_path,
    )["item"]
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (False, "approval_missing"))

    payload = self_healing_worker.process_once(runtime_root=tmp_path)

    assert payload["result"] == "blocked"
    assert payload["reason"] == "approval_missing"
    queue_item = _load_queue_item(tmp_path, str(item["id"]))
    assert queue_item["state"] == "blocked"


def test_state_transitions_correct(tmp_path, monkeypatch) -> None:
    item = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )["item"]
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (True, "approved_and_available"))
    monkeypatch.setattr(self_healing_worker, "_execute_action", lambda action: (False, "boom"))

    payload = self_healing_worker.process_once(runtime_root=tmp_path)

    assert payload["result"] == "failed"
    queue_item = _load_queue_item(tmp_path, str(item["id"]))
    assert queue_item["state"] == "failed"
    assert int(queue_item["attempts"]) == 1


def test_remediation_history_logged(tmp_path, monkeypatch) -> None:
    remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (True, "approved_and_available"))
    monkeypatch.setattr(self_healing_worker, "_execute_action", lambda action: (True, "ok"))

    self_healing_worker.process_once(runtime_root=tmp_path)

    rows = _load_history_rows(tmp_path)
    assert rows
    last = rows[-1]
    assert last["queue_id"].startswith("rq_")
    assert last["result"] == "success"


def test_queue_updated_correctly(tmp_path, monkeypatch) -> None:
    first = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )["item"]
    second = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )["item"]
    monkeypatch.setattr(self_healing_worker, "_policy_allows", lambda **kwargs: (True, "approved_and_available"))
    monkeypatch.setattr(self_healing_worker, "_execute_action", lambda action: (True, "ok"))

    self_healing_worker.process_once(runtime_root=tmp_path)

    first_item = _load_queue_item(tmp_path, str(first["id"]))
    second_item = _load_queue_item(tmp_path, str(second["id"]))
    assert first_item["state"] == "success"
    assert second_item["state"] == "queued"
