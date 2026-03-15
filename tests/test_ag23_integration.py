import json
import os
import sys
from pathlib import Path

import pytest

# Make repo-root imports work when running this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _state_dir() -> Path:
    return Path(os.environ["LUKA_RUNTIME_ROOT"]) / "state"


def _read_json(path: Path):
    return json.loads(path.read_text())


def _read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.fixture
def isolated_runtime_root(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    return runtime_root


def _policy(
    policy_id: str,
    *,
    rule: str = "allow_default",
    confidence: float = 0.95,
    activated_at: str = "2026-03-15T22:56:08Z",
    activated_by: str = "operator",
    status: str = "ACTIVE",
):
    return {
        "policy_id": policy_id,
        "rule": rule,
        "confidence": confidence,
        "activated_at": activated_at,
        "activated_by": activated_by,
        "status": status,
    }


def test_deprecate_policy_marks_status_and_logs(isolated_runtime_root):
    from core.policy.policy_lifecycle import deprecate_policy
    from core.policy.policy_registry import get_policy, register_policy

    policy_id = "policy_deprecate_1"
    register_policy(policy_id, _policy(policy_id))

    result = deprecate_policy(policy_id, "operator_1", reason="soft retire")

    assert result["ok"] is True
    stored = get_policy(policy_id)
    assert stored is not None
    assert stored["status"] == "DEPRECATED"

    log_path = _state_dir() / "policy_activation_log.jsonl"
    entries = _read_jsonl(log_path)
    assert entries, "policy_activation_log.jsonl should contain at least one entry"
    assert entries[-1]["status"] == "DEPRECATED"
    assert entries[-1]["policy_id"] == policy_id


def test_revoke_policy_marks_status_and_logs(isolated_runtime_root):
    from core.policy.policy_lifecycle import revoke_policy
    from core.policy.policy_registry import get_policy, register_policy

    policy_id = "policy_revoke_1"
    register_policy(policy_id, _policy(policy_id))

    result = revoke_policy(policy_id, "operator_2", reason="hard revoke")

    assert result["ok"] is True
    stored = get_policy(policy_id)
    assert stored is not None
    assert stored["status"] == "REVOKED"

    log_path = _state_dir() / "policy_activation_log.jsonl"
    entries = _read_jsonl(log_path)
    assert entries, "policy_activation_log.jsonl should contain at least one entry"
    assert entries[-1]["status"] == "REVOKED"
    assert entries[-1]["policy_id"] == policy_id


def test_supersede_policy_marks_old_policy_and_logs(isolated_runtime_root):
    from core.policy.policy_lifecycle import supersede_policy
    from core.policy.policy_registry import get_policy, register_policy

    old_policy_id = "policy_old_1"
    new_policy_id = "policy_new_1"

    register_policy(old_policy_id, _policy(old_policy_id))
    register_policy(new_policy_id, _policy(new_policy_id, rule="allow_newer"))

    result = supersede_policy(old_policy_id, new_policy_id, "operator_3")

    assert result["ok"] is True
    old_policy = get_policy(old_policy_id)
    assert old_policy is not None
    assert old_policy["status"] == "SUPERSEDED"
    assert old_policy["superseded_by"] == new_policy_id

    log_path = _state_dir() / "policy_activation_log.jsonl"
    entries = _read_jsonl(log_path)
    assert entries, "policy_activation_log.jsonl should contain at least one entry"
    assert entries[-1]["status"] == "SUPERSEDED"
    assert entries[-1]["policy_id"] == old_policy_id
    assert entries[-1]["new_policy_id"] == new_policy_id


def test_list_policies_by_status_filters_correctly(isolated_runtime_root):
    from core.policy.policy_lifecycle import list_policies_by_status
    from core.policy.policy_registry import register_policy

    register_policy("p_active", _policy("p_active", status="ACTIVE"))
    register_policy("p_deprecated", _policy("p_deprecated", status="DEPRECATED"))
    register_policy("p_revoked", _policy("p_revoked", status="REVOKED"))

    active = {p["policy_id"] for p in list_policies_by_status("ACTIVE")}
    deprecated = {p["policy_id"] for p in list_policies_by_status("DEPRECATED")}
    revoked = {p["policy_id"] for p in list_policies_by_status("REVOKED")}

    assert active == {"p_active"}
    assert deprecated == {"p_deprecated"}
    assert revoked == {"p_revoked"}


def test_plan_allowed_ignores_inactive_policies(isolated_runtime_root):
    from core.policy.policy_gate import plan_allowed
    from core.policy.policy_registry import register_policy

    register_policy(
        "deny_delete_deprecated",
        _policy(
            "deny_delete_deprecated",
            rule="deny_delete_repo",
            status="DEPRECATED",
        ),
    )

    steps = [{"action": "delete_repo"}]
    verdict = plan_allowed({"steps": steps})

    assert verdict != "BLOCK"


def test_plan_allowed_blocks_on_active_promoted_policy(isolated_runtime_root):
    from core.policy.policy_gate import plan_allowed
    from core.policy.policy_registry import register_policy

    register_policy(
        "deny_delete_active",
        _policy(
            "deny_delete_active",
            rule="deny_delete_repo",
            status="ACTIVE",
        ),
    )

    steps = [{"action": "delete_repo"}]
    verdict = plan_allowed({"steps": steps})

    assert verdict == "BLOCK"


def test_expire_policies_marks_stale_policy_expired(isolated_runtime_root):
    from core.policy.policy_lifecycle import expire_policies
    from core.policy.policy_registry import get_policy, register_policy

    policy_id = "policy_expire_1"
    register_policy(
        policy_id,
        _policy(
            policy_id,
            activated_at="2020-01-01T00:00:00Z",
            status="ACTIVE",
        ),
    )

    result = expire_policies(ttl_seconds=1)

    # Support either a structured result or a simpler return.
    assert result is not None

    stored = get_policy(policy_id)
    assert stored is not None
    assert stored["status"] == "EXPIRED"
