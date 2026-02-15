"""Chat bot helpers for NLP control-plane previews and prompt generation.

This module provides:
1) a bot facade that converts raw user utterances into normalized + task preview
   structures using existing control-plane functions, and
2) a transformer that converts manual numbered task lists into a fail-closed,
   execution-ready Codex prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import re

from .normalizer import build_task_spec, normalize_input


@dataclass(frozen=True)
class BotReply:
    """Structured bot response for terminal/chat surfaces."""

    message: str
    normalized: Dict[str, Any]
    task_spec: Dict[str, Any]


def build_bot_reply(raw_input: str, preview_id: str) -> BotReply:
    """Build a user-facing bot reply using repo-native functions."""

    normalized = normalize_input(raw_input)
    task_spec = build_task_spec(normalized, preview_id)

    risk = normalized.get("risk", "unknown")
    intent = normalized.get("intent", "unknown")
    lane = task_spec.get("lane", "unknown")
    task_id = task_spec.get("task_id", "unknown")

    message = (
        f"Intent={intent} | Risk={risk} | Lane={lane} | "
        f"TaskPreview={task_id}"
    )

    return BotReply(message=message, normalized=normalized, task_spec=task_spec)


def extract_numbered_tasks(raw_text: str) -> List[str]:
    """Extract ordered tasks from common numbered-list formats.

    Supports numbered headers (`1.`, `1)`) and preserves indented detail lines
    (such as `- sub-bullets`) under the latest numbered task.
    """

    tasks: List[str] = []
    current_lines: List[str] = []

    def flush_current() -> None:
        if current_lines:
            tasks.append("\n".join(current_lines).strip())
            current_lines.clear()

    for raw_line in raw_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        header_match = re.match(r"^\d+[\.)]\s+(.*)$", stripped)
        if header_match:
            flush_current()
            current_lines.append(header_match.group(1).strip())
            continue

        if current_lines:
            current_lines.append(stripped)

    flush_current()
    return tasks


def build_unified_execution_prompt(task_list_text: str, repo_name: str = "0luka") -> str:
    """Transform manual task list text into an execution-ready prompt.

    If no numbered entries are found, the entire input is treated as one task.
    """

    tasks = extract_numbered_tasks(task_list_text)
    if not tasks and task_list_text.strip():
        tasks = [task_list_text.strip()]

    task_lines = "\n".join(f"{i}) {task}" for i, task in enumerate(tasks, start=1))
    if not task_lines:
        task_lines = "1) (No tasks detected in input)"

    return (
        f"You are given a list of sequential tasks to perform on the {repo_name} repo. "
        "Execute each in order and stop fail-closed if any step fails. "
        "Provide clear proof outputs.\n\n"
        "Tasks:\n\n"
        f"{task_lines}\n\n"
        "General rules:\n"
        "- Run shell/python commands with `set -euo pipefail` where applicable.\n"
        "- If a step fails, stop and return:\n"
        "  - failing command\n"
        "  - stderr snippet\n"
        "  - path to any partial evidence\n"
        "- When producing summaries, include:\n"
        "  - HEAD SHA\n"
        "  - branch name\n"
        "  - exit codes\n"
        "  - evidence file paths\n\n"
        "Return for each step:\n"
        "- command run\n"
        "- exit code\n"
        "- key stdout/stderr\n"
        "- audit summary\n"
    )
