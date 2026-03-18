import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
from pathlib import Path
from core.config import RUNTIME_LOGS_DIR
from core.orchestrator_v1 import handle_request
from core.replay_engine import replay_trace

_FALLBACK_RISK = {"risk_level": "medium", "guard_action": "review", "reason": "unknown intent"}
_FALLBACK_AGENT = {"agent": "system", "mode": "fallback"}
_FEED = RUNTIME_LOGS_DIR / "activity_feed.jsonl"


def _next_step(mode: str, result: dict) -> str:
    status = (result or {}).get("status", "")
    if status == "rejected":
        return "clarify or refine request"
    if status == "blocked":
        return "clarify or override safely"
    if mode == "apply" and status == "success":
        return "inspect result"
    if mode == "apply" and status == "failed":
        return "debug command result"
    return "review planned command"


def _last_trace_id() -> str | None:
    if not _FEED.exists():
        return None
    last = None
    with open(_FEED) as f:
        for line in f:
            try:
                d = json.loads(line)
                if d.get("trace_id"):
                    last = d["trace_id"]
            except json.JSONDecodeError:
                continue
    return last


def main():

    # --- read input ---
    human_input = input().strip()

    # --- replay-last flag ---
    if "--replay-last" in human_input:
        tid = _last_trace_id()
        if tid is None:
            print(json.dumps({"error": "no traces found in feed"}))
            return
        print(json.dumps(replay_trace(tid), indent=2))
        return

    # --- replay-trace-id flag ---
    if "--replay-trace-id" in human_input:
        parts = human_input.split("--replay-trace-id", 1)
        tid = parts[1].strip().split()[0] if parts[1].strip() else ""
        if not tid:
            print(json.dumps({"error": "missing trace_id after --replay-trace-id"}))
            return
        print(json.dumps(replay_trace(tid), indent=2))
        return

    # --- context ---
    context = {
        "cwd": os.getcwd()
    }

    # --- mode detection ---
    mode = "plan_only"
    emit_trace_id_only = False

    if "--apply" in human_input:
        mode = "apply"
        human_input = human_input.replace("--apply", "").strip()

    if "--verify" in human_input:
        mode = "verify"
        human_input = human_input.replace("--verify", "").strip()

    if "--emit-trace-id-only" in human_input:
        emit_trace_id_only = True
        human_input = human_input.replace("--emit-trace-id-only", "").strip()

    # --- orchestrator ---
    res = handle_request(human_input, context, mode)

    # --- emit-trace-id-only early return ---
    if emit_trace_id_only:
        print(json.dumps({"trace_id": res.get("trace_id")}))
        return

    # --- normalized_task with fallback ---
    task = res.get("normalized_task") or {}
    normalized_task = {
        "type": task.get("type") or "unknown",
        "intent": task.get("intent") or human_input,
        "scope": task.get("scope") or context["cwd"],
        "risk": task.get("risk") or "unknown",
    }

    # --- command fields ---
    command = res.get("command")
    command_source = command.get("source") if command else "none"
    command_out = (
        {"name": command.get("name"), "args": command.get("args", [])}
        if command and command.get("name")
        else None
    )

    # --- result with fallback ---
    result = res.get("result") or {"status": "rejected", "reason": "unknown_intent"}

    # --- enforce output contract ---
    output = {
        "trace_id": res.get("trace_id"),
        "execution_mode": mode,
        "intent": human_input,
        "normalized_task": normalized_task,
        "command_source": command_source,
        "command": command_out,
        "result": result,
        "risk": res.get("risk") or _FALLBACK_RISK,
        "agent": res.get("agent") or _FALLBACK_AGENT,
        "next_step": _next_step(mode, result),
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
