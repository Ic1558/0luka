"""Contract-safe NLP bot helpers for preview delegation and prompt generation.

Contract surface in this module:
1) ``build_bot_reply`` delegates normalization/spec construction to existing
   core functions and returns a deterministic summary object.
2) ``extract_numbered_tasks`` parses valid numbered lines (``1.`` / ``1)``)
   and preserves indented detail lines (bullets) under the latest task.
3) ``build_unified_execution_prompt`` creates a fail-closed execution template
   that explicitly asks for command + evidence proof.

Determinism expectations:
- No network or filesystem I/O.
- No subprocess execution.
- Same inputs produce the same outputs.

Out-of-scope by design:
- Rich markdown parsing beyond numbered-line matching and subtask preservation.
- Any autonomous execution of extracted tasks.
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
    """Build a deterministic preview reply by delegating to existing core APIs.

    Inputs:
    - ``raw_input``: original user text (passed through to ``normalize_input``).
    - ``preview_id``: preview correlation id (forwarded to ``build_task_spec``).

    Output:
    - ``BotReply`` with a summary ``message`` and raw delegated outputs
      (``normalized`` + ``task_spec``).

    Fail-closed behavior:
    - Missing intent/risk/lane/task fields are rendered as ``unknown`` instead
      of inferring new values.

    Out-of-scope:
    - Any mutation, dispatch, or execution side effects.
    """

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
    """Extract ordered task strings from strictly numbered lines and their details.

    Inputs:
    - ``raw_text``: multiline text that may contain human-written steps.

    Output:
    - ordered list of task text captured from lines matching ``^\\d+[.)]\\s+``,
      preserving any subsequent non-numbered lines as details.

    Fail-closed behavior:
    - Empty/whitespace-only input returns an empty list.

    Determinism expectations:
    - Pure parsing with no external dependencies and stable ordering.

    Out-of-scope:
    - Supporting nested numbered lists or complex markdown.
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
    """Create a deterministic fail-closed execution prompt from raw task text.

    Inputs:
    - ``task_list_text``: raw manual task description.
    - ``repo_name``: repository label rendered into the prompt header.

    Output:
    - string prompt containing:
      - ordered task lines,
      - explicit fail-closed stop condition,
      - mandatory proof fields (HEAD SHA, branch, exit codes, evidence paths).

    Fail-closed behavior:
    - If numbered parsing yields no tasks and input is non-empty, treat the full
      text as one task (avoid silent loss).
    - If input is empty/whitespace, emit a placeholder task line.

    Determinism expectations:
    - Prompt wording is static except for ``repo_name`` and rendered tasks.

    Out-of-scope:
    - Executing tasks, validating command correctness, or policy approval.
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
