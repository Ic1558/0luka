"""Unit tests for the NLP control-plane bot helper."""

from modules.nlp_control_plane.core.bot import (
    build_bot_reply,
    build_unified_execution_prompt,
    extract_numbered_tasks,
)


def test_build_bot_reply_uses_existing_normalizer_functions(monkeypatch):
    captured = {}

    def fake_normalize(raw_input):
        captured["raw_input"] = raw_input
        return {
            "intent": "status_check",
            "tool": "status_reader",
            "risk": "low",
            "params": {"raw": raw_input},
        }

    def fake_build_task_spec(normalized, preview_id):
        captured["normalized"] = normalized
        captured["preview_id"] = preview_id
        return {
            "task_id": "task_test_001",
            "lane": "task",
            "intent": normalized["intent"],
            "operations": [],
            "author": "gmx",
            "created_at_utc": "2026-01-01T00:00:00Z",
            "reply_to": "interface/outbox/tasks",
            "preview_id": preview_id,
        }

    monkeypatch.setattr("modules.nlp_control_plane.core.bot.normalize_input", fake_normalize)
    monkeypatch.setattr("modules.nlp_control_plane.core.bot.build_task_spec", fake_build_task_spec)

    reply = build_bot_reply("check status", "preview-123")

    assert captured["raw_input"] == "check status"
    assert captured["preview_id"] == "preview-123"
    assert reply.normalized["intent"] == "status_check"
    assert reply.task_spec["task_id"] == "task_test_001"
    assert "Intent=status_check" in reply.message
    assert "Risk=low" in reply.message


def test_build_bot_reply_handles_unknown_fields(monkeypatch):
    monkeypatch.setattr(
        "modules.nlp_control_plane.core.bot.normalize_input",
        lambda _: {"tool": "unknown", "params": {}},
    )
    monkeypatch.setattr(
        "modules.nlp_control_plane.core.bot.build_task_spec",
        lambda *_: {"operations": []},
    )

    reply = build_bot_reply("???", "preview-unknown")

    assert reply.message.startswith("Intent=unknown")
    assert "Risk=unknown" in reply.message
    assert "Lane=unknown" in reply.message


def test_extract_numbered_tasks_supports_dot_and_paren_formats():
    text = """
    1. Execute post-merge verification on main
    2) Check commit history integrity
    3. Assess and recover registry schema consistency
    """

    tasks = extract_numbered_tasks(text)

    assert tasks == [
        "Execute post-merge verification on main",
        "Check commit history integrity",
        "Assess and recover registry schema consistency",
    ]


def test_extract_numbered_tasks_preserves_nested_details():
    text = """
    1. Execute post-merge verification on main
       - checkout main
       - run strict DoD
    2) Check commit history integrity
       - show last 10 commits
    """

    tasks = extract_numbered_tasks(text)

    assert tasks == [
        "Execute post-merge verification on main\n- checkout main\n- run strict DoD",
        "Check commit history integrity\n- show last 10 commits",
    ]


def test_build_unified_execution_prompt_preserves_task_detail_lines():
    prompt = build_unified_execution_prompt(
        "1. Step one\n   - detail A\n2. Step two",
        repo_name="0luka",
    )

    assert "1) Step one\n- detail A" in prompt
    assert "2) Step two" in prompt


def test_build_unified_execution_prompt_formats_fail_closed_template():
    prompt = build_unified_execution_prompt(
        "1. step one\n2. step two",
        repo_name="0luka",
    )

    assert "sequential tasks to perform on the 0luka repo" in prompt
    assert "1) step one" in prompt
    assert "2) step two" in prompt
    assert "stop fail-closed" in prompt
    assert "HEAD SHA" in prompt
