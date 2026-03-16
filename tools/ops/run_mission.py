#!/usr/bin/env python3
"""AG-P7: run_mission.py — canonical operator mission runner.

Usage:
  dotenvx run --env-file ~/.env -- python3 tools/ops/run_mission.py \\
    --prompt "YOUR_PROMPT" \\
    --operator-id boss \\
    [--notify] \\
    [--provider claude] \\
    [--mission-id my_mission]

Writes artifact to observability/artifacts/missions/<mission_id>.json
Always exits 0. Errors recorded in result.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact_dir() -> Path:
    d = ROOT / "observability" / "artifacts" / "missions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _notify(result: dict, token: str, chat_id: str) -> dict:
    try:
        from runtime.tools.bootstrap import bootstrap_tools
        from runtime.tools.dispatcher import dispatch_tool
        bootstrap_tools()
        response_text = (result.get("response") or "")[:200]
        status = result.get("status", "unknown")
        msg = f"[{result.get('mission_id','?')}] {status}: {response_text}"
        return dispatch_tool(
            "telegram_send",
            {"message": msg, "bot_token": token, "chat_id": chat_id},
            operator_id=result.get("operator_id", "boss"),
            inference_id=result.get("inference_id"),
        )
    except Exception as exc:
        return {"error": str(exc)}


def run_mission(
    prompt: str,
    *,
    operator_id: str = "boss",
    provider: str = "claude",
    mission_id: str | None = None,
    notify: bool = False,
) -> dict:
    mission_id = mission_id or f"m_{uuid.uuid4().hex[:10]}"
    ts_start = _now()

    try:
        from runtime.operator_task import submit_operator_task
        task = submit_operator_task(prompt, operator_id=operator_id, provider=provider)
    except Exception as exc:
        task = {"status": "error", "error": str(exc)}

    notify_result = None
    if notify and task.get("status") == "executed":
        token = os.environ.get("TELEGRAM_BOT_TOKEN_GGMESH", "")
        chat_id = "-1002324084957"
        notify_result = _notify({**task, "mission_id": mission_id}, token, chat_id)

    result = {
        "mission_id": mission_id,
        "operator_id": operator_id,
        "provider": provider,
        "prompt": prompt,
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "block_reason": task.get("block_reason"),
        "inference_id": task.get("inference_id"),
        "response": task.get("response"),
        "notify_result": notify_result,
        "ts_start": ts_start,
        "ts_end": _now(),
    }

    artifact = _artifact_dir() / f"{mission_id}.json"
    tmp = artifact.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2))
    tmp.replace(artifact)
    result["artifact_path"] = str(artifact)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sovereign operator mission runner")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--operator-id", default="boss")
    parser.add_argument("--provider", default="claude")
    parser.add_argument("--mission-id", default=None)
    parser.add_argument("--notify", action="store_true", help="Send result to Telegram")
    args = parser.parse_args()

    result = run_mission(
        args.prompt,
        operator_id=args.operator_id,
        provider=args.provider,
        mission_id=args.mission_id,
        notify=args.notify,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
