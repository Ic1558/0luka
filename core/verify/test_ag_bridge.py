from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.bridge.ag_bridge import dispatch  # noqa: E402


def _request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "00000000-0000-0000-0000-000000000111",
        "source": "antigravity",
        "agent": "cole",
        "task": "cole.search_docs",
        "args": {"query": "runtime policy"},
        "created_at_utc": "2026-03-14T00:00:00Z",
    }
    base.update(overrides)
    return base


def _write_policy(path: Path, *, freeze_state: bool) -> None:
    path.write_text(
        "\n".join(
            [
                'version: "1.0"',
                'updated_at: "2026-03-14T00:00:00+07:00"',
                "defaults:",
                "  deny_by_default: true",
                f"  freeze_state: {'true' if freeze_state else 'false'}",
                "  max_task_size_bytes: 1048576",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_dispatch_rejects_invalid_source() -> None:
    response = dispatch(_request(source="other"))
    assert response.status == "rejected"
    assert response.error == "invalid:source"


def test_dispatch_rejects_unknown_agent() -> None:
    response = dispatch(_request(agent="gmx"))
    assert response.status == "rejected"
    assert response.error == "invalid:agent:gmx"


def test_dispatch_rejects_unknown_task() -> None:
    response = dispatch(_request(task="paula.run_strategy"))
    assert response.status == "rejected"
    assert response.error == "invalid:task:paula.run_strategy"


def test_dispatch_blocks_on_policy_freeze(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, freeze_state=True)
    response = dispatch(_request(), policy_path=policy_path)
    assert response.status == "blocked"
    assert response.policy_blocked is True


def test_dispatch_accepted_valid_request(tmp_path: Path, monkeypatch) -> None:
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, freeze_state=False)

    monkeypatch.setattr(
        "tools.bridge.ag_bridge.submit_task",
        lambda task, task_id=None: {"task_id": "test-123"},
    )

    response = dispatch(_request(), policy_path=policy_path)
    assert response.status == "accepted"
    assert response.task_id == "test-123"
    assert response.error is None

