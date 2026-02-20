"""Unit tests for the NLP control-plane bot helper."""

from pathlib import Path
import subprocess
import sys

from modules.nlp_control_plane.core.bot import (
    build_bot_reply,
    build_unified_execution_prompt,
    extract_numbered_tasks,
)


def test_build_bot_reply_uses_existing_normalizer_functions(monkeypatch):
    captured = {}
    normalize_calls = 0
    build_spec_calls = 0

    def fake_normalize(raw_input):
        nonlocal normalize_calls
        normalize_calls += 1
        captured["raw_input"] = raw_input
        return {
            "intent": "status_check",
            "tool": "status_reader",
            "risk": "low",
            "params": {"raw": raw_input},
        }

    def fake_build_task_spec(normalized, preview_id):
        nonlocal build_spec_calls
        build_spec_calls += 1
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
    assert normalize_calls == 1
    assert build_spec_calls == 1
    assert captured["normalized"] == reply.normalized
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


def test_extract_numbered_tasks_empty_and_whitespace_input():
    assert extract_numbered_tasks("") == []
    assert extract_numbered_tasks("  \n\t \n") == []


def test_extract_numbered_tasks_rejects_malformed_numbering():
    text = "\n".join(
        [
            "1.. malformed",
            "1- malformed",
            "1 ) malformed",
            "1)valid task",
            "2) valid task",
        ]
    )

    tasks = extract_numbered_tasks(text)

    assert tasks == ["valid task"]


def test_extract_numbered_tasks_mixed_bullet_styles_preserves_details():
    text = "\n".join(
        [
            "1. first task",
            "- detail A",
            "2) second task",
            "* detail B",
            "3. third task",
        ]
    )

    expected = [
        "first task\n- detail A",
        "second task\n* detail B",
        "third task",
    ]
    assert extract_numbered_tasks(text) == expected


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


def test_build_unified_execution_prompt_handles_empty_and_whitespace():
    empty_prompt = build_unified_execution_prompt("")
    whitespace_prompt = build_unified_execution_prompt(" \n\t ")

    assert "1) (No tasks detected in input)" in empty_prompt
    assert "1) (No tasks detected in input)" in whitespace_prompt
    assert "stop fail-closed" in whitespace_prompt
    assert "failing command" in whitespace_prompt
    assert "stderr snippet" in whitespace_prompt
    assert "HEAD SHA" in whitespace_prompt
    assert "branch name" in whitespace_prompt
    assert "exit codes" in whitespace_prompt
    assert "evidence file paths" in whitespace_prompt


def test_build_unified_execution_prompt_treats_non_numbered_text_as_one_task():
    prompt = build_unified_execution_prompt("manual fallback task")

    # The behavior should be that if no numbered headers are found, 
    # extract_numbered_tasks returns [], then prompt treats raw input as one task.
    assert "1) manual fallback task" in prompt
    assert "2) " not in prompt


def test_importing_nlp_module_does_not_eager_import_fastapi():
    repo_root = Path(__file__).resolve().parents[3]
    code = (
        "import importlib, sys\n"
        "importlib.import_module('modules.nlp_control_plane')\n"
        "importlib.import_module('modules.nlp_control_plane.core')\n"
        "print('fastapi' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"
