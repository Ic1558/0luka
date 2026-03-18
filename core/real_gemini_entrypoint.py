"""
real_gemini_entrypoint.py — Explicit Gemini CLI entry surface.

Disambiguates the intended Gemini entry path from the internal stdin pipe surface.
Delegates to the same orchestrator pipeline as cli_entrypoint.py.

Supported flags:
  --input "text"          Direct text input (preferred Gemini surface)
  --apply                 Execute mode
  --verify                Verify mode
  --replay-last           Replay last trace
  --replay-trace-id <ID>  Replay specific trace_id
  --emit-trace-id-only    Return only {"trace_id": ...}
  --dispatch              Append dispatch_payload to output

Backward compat:
  Reads from stdin if --input is not provided (same behavior as cli_entrypoint.py).

Output contract: identical to cli_entrypoint.py + optional dispatch_payload field.
"""

import argparse
import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pathlib import Path
from core.orchestrator_v1 import handle_request
from core.replay_engine import replay_trace

_FALLBACK_RISK = {"risk_level": "medium", "guard_action": "review", "reason": "unknown intent"}
_FALLBACK_AGENT = {"agent": "system", "mode": "fallback"}
_FEED = Path.home() / "0luka/observability/activity_feed.jsonl"


def _last_trace_id():
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


def _next_step(mode, result):
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


def run(human_input, mode: str = "plan_only", emit_trace_id_only: bool = False,
        include_dispatch: bool = False) -> dict:
    """
    Execute a request through the orchestrator pipeline.

    Args:
        human_input: str, list of str (argv-style, joined with space), or dict with "intent" key.
        mode: "plan_only" | "apply" | "verify"
        emit_trace_id_only: If True, return only {"trace_id": ...}
        include_dispatch: If True, append dispatch_payload to output.

    Returns:
        Structured JSON-serializable result dict.
    """
    if isinstance(human_input, list):
        human_input = " ".join(str(t) for t in human_input)
    elif isinstance(human_input, dict):
        human_input = human_input.get("intent") or str(human_input)
    elif not isinstance(human_input, str):
        human_input = str(human_input)

    context = {"cwd": os.getcwd()}
    res = handle_request(human_input, context, mode)

    if emit_trace_id_only:
        return {"trace_id": res.get("trace_id")}

    task = res.get("normalized_task") or {}
    normalized_task = {
        "type": task.get("type") or "unknown",
        "intent": task.get("intent") or human_input,
        "scope": task.get("scope") or context["cwd"],
        "risk": task.get("risk") or "unknown",
    }
    command = res.get("command")
    command_out = (
        {"name": command.get("name"), "args": command.get("args", [])}
        if command and command.get("name")
        else None
    )
    result_field = res.get("result") or {"status": "rejected", "reason": "unknown_intent"}

    output = {
        "trace_id": res.get("trace_id"),
        "execution_mode": mode,
        "intent": human_input,
        "normalized_task": normalized_task,
        "command_source": command.get("source") if command else "none",
        "command": command_out,
        "result": result_field,
        "risk": res.get("risk") or _FALLBACK_RISK,
        "agent": res.get("agent") or _FALLBACK_AGENT,
        "next_step": _next_step(mode, result_field),
    }

    if include_dispatch:
        from core.agent_dispatch_bridge import create_dispatch_payload
        dispatch_input = {
            "trace_id": output["trace_id"],
            "intent": human_input,
            "normalized_task": normalized_task,
            **result_field,
        }
        output["dispatch_payload"] = create_dispatch_payload(dispatch_input)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Gemini CLI — explicit entry surface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", "-i", dest="user_input", default=None,
                        help="Request text (reads stdin if not provided)")
    parser.add_argument("--apply", action="store_true", help="Execute mode (not plan-only)")
    parser.add_argument("--verify", action="store_true", help="Verify mode")
    parser.add_argument("--replay-last", action="store_true", help="Replay last trace")
    parser.add_argument("--replay-trace-id", dest="replay_id", default=None,
                        metavar="TRACE_ID", help="Replay specific trace_id")
    parser.add_argument("--emit-trace-id-only", action="store_true",
                        help="Return only {\"trace_id\": ...}")
    parser.add_argument("--dispatch", action="store_true",
                        help="Append dispatch_payload to output")

    args = parser.parse_args()

    # --- replay paths ---
    if args.replay_last:
        tid = _last_trace_id()
        if tid is None:
            print(json.dumps({"error": "no traces found in feed"}))
            return
        print(json.dumps(replay_trace(tid), indent=2))
        return

    if args.replay_id:
        print(json.dumps(replay_trace(args.replay_id), indent=2))
        return

    # --- input resolution ---
    if args.user_input is not None:
        human_input = args.user_input.strip()
    else:
        human_input = sys.stdin.read().strip()

    mode = "plan_only"
    if args.apply:
        mode = "apply"
    elif args.verify:
        mode = "verify"

    result = run(
        human_input,
        mode=mode,
        emit_trace_id_only=args.emit_trace_id_only,
        include_dispatch=args.dispatch,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
