# plugins/executors/mcp_exec.py
from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# ========= Paths (0luka canonical) =========
ROOT = Path.home() / "0luka"

OBS = ROOT / "observability"
AUDIT = OBS / "audit"
TELEMETRY = OBS / "telemetry"
LEDGER = OBS / "stl" / "ledger" / "global_beacon.jsonl"

DEFAULT_TASK_INBOX = OBS / "antigravity_tmp" / "tasks_inbox"

DEFAULT_SOCK = str(ROOT / "runtime" / "sock" / "gate_runner.sock")


# ========= RPC Client (exact protocol v0.4 per your signature) =========
class RPCClient:
    CLIENT_ID = "rpc_client"
    CLIENT_PATH = os.path.abspath(__file__)

    def __init__(self, sock_path: str = DEFAULT_SOCK):
        self.sock_path = sock_path

    def call(self, cmd: str, **kwargs):
        if not os.path.exists(self.sock_path):
            return {"error": f"Socket not found at {self.sock_path}"}

        client = None
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(self.sock_path)

            request = {"cmd": cmd, **kwargs}
            request["client_id"] = self.CLIENT_ID
            request["client_path"] = self.CLIENT_PATH

            payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
            msg = struct.pack(">I", len(payload)) + payload
            client.sendall(msg)

            len_bytes = client.recv(4)
            if not len_bytes:
                return {"error": "No response from daemon"}

            resp_len = struct.unpack(">I", len_bytes)[0]

            resp_data = b""
            while len(resp_data) < resp_len:
                chunk = client.recv(min(4096, resp_len - len(resp_data)))
                if not chunk:
                    break
                resp_data += chunk

            if len(resp_data) != resp_len:
                return {"error": f"Incomplete response (expected {resp_len}, got {len(resp_data)})"}

            return json.loads(resp_data.decode("utf-8"))
        except Exception as e:
            return {"error": str(e)}
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass


# ========= Task model =========
@dataclass(frozen=True)
class Task:
    task_id: str
    module: str
    action: str
    args: Dict[str, Any]
    ts: str
    requested_by: str = "unknown"
    source_path: str = ""


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_task_json(path: Path) -> Task:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Task(
        task_id=str(raw["task_id"]),
        module=str(raw["module"]),
        action=str(raw["action"]),
        args=dict(raw.get("args", {})),
        ts=str(raw.get("ts", _now_iso_z())),
        requested_by=str(raw.get("requested_by", "unknown")),
        source_path=str(path),
    )


def pick_latest_task(inbox: Path) -> Path:
    candidates = sorted(inbox.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No *.json tasks found in {inbox}")
    return candidates[0]


# ========= Allowlist mapping =========
def map_action_to_tool(action: str) -> Path:
    """
    Explicit allowlist only. Add new actions intentionally.
    """
    # NOTE: Path corrected for generate_followup_data.zsh
    allow: Dict[str, Path] = {
        "action.followup.generate": ROOT / "tools" / "claude_tools" / "generate_followup_data.zsh",
        "action.ram.snapshot": ROOT / "tools" / "ram_monitor.zsh",
        "action.mls.watch": ROOT / "tools" / "mls_file_watcher.zsh",
    }
    if action not in allow:
        raise ValueError(f"Action not allowed: {action}")
    return allow[action]


# ========= Governance =========
def authorize_or_raise(client: RPCClient, task: Task) -> Dict[str, Any]:
    resp = client.call("authorize", action=task.action, args=task.args)

    # Hard reject on transport or daemon errors
    if isinstance(resp, dict) and resp.get("error"):
        raise PermissionError(f"authorize error: {resp.get('error')}")

    # Support common shapes without guessing too much
    # If daemon returns {"ok": false} or {"allowed": false}, reject.
    if isinstance(resp, dict):
        if resp.get("ok") is False:
            raise PermissionError(f"authorize denied (ok=false): {resp}")
        if resp.get("allowed") is False:
            raise PermissionError(f"authorize denied (allowed=false): {resp}")

    return resp


# ========= Execution =========
def run_tool_zsh(tool_path: Path, task: Task) -> Dict[str, Any]:
    if not tool_path.exists():
        raise FileNotFoundError(f"Tool not found: {tool_path}")

    AUDIT.mkdir(parents=True, exist_ok=True)

    safe_action = task.action.replace(".", "_").replace("/", "_")
    out_log = AUDIT / f"{task.task_id}_{safe_action}.out.log"
    err_log = AUDIT / f"{task.task_id}_{safe_action}.err.log"

    env = os.environ.copy()
    env["LUKA_TASK_ID"] = task.task_id
    env["LUKA_MODULE"] = task.module
    env["LUKA_ACTION"] = task.action
    env["LUKA_ARGS_JSON"] = json.dumps(task.args, ensure_ascii=False)

    cmd = ["/usr/bin/env", "zsh", str(tool_path)]

    with out_log.open("wb") as fo, err_log.open("wb") as fe:
        p = subprocess.run(cmd, env=env, stdout=fo, stderr=fe)

    return {
        "exit_code": int(p.returncode),
        "tool": str(tool_path),
        "audit_out": str(out_log),
        "audit_err": str(err_log),
    }


# ========= Telemetry + Ledger =========
def write_telemetry_latest(task: Task, auth_resp: Any, run_resp: Optional[Dict[str, Any]], rejected: bool, reason: str) -> Path:
    TELEMETRY.mkdir(parents=True, exist_ok=True)
    # Keep module name compact for filenames
    mod_tail = task.module.split(".")[-1] if task.module else "task"
    out = TELEMETRY / f"{mod_tail}.latest.json"

    payload: Dict[str, Any] = {
        "ts": _now_iso_z(),
        "task": {
            "task_id": task.task_id,
            "module": task.module,
            "action": task.action,
            "args": task.args,
            "requested_by": task.requested_by,
            "source_path": task.source_path,
            "declared_ts": task.ts,
        },
        "governance": {
            "sock": DEFAULT_SOCK,
            "authorize_response": auth_resp,
        },
        "result": run_resp if run_resp is not None else {},
        "ok": (not rejected) and (run_resp is not None) and (run_resp.get("exit_code") == 0),
        "rejected": rejected,
        "reason": reason,
    }

    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def append_beacon(task: Task, ok: bool, event: str, detail: Dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "ts": _now_iso_z(),
        "event": event,  # e.g., "task_committed" or "task_rejected"
        "task_id": task.task_id,
        "module": task.module,
        "action": task.action,
        "ok": bool(ok),
        "detail": detail,
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


# ========= Main =========
def main(argv: list[str]) -> int:
    inbox = Path(os.environ.get("LUKA_TASK_INBOX", str(DEFAULT_TASK_INBOX)))
    sock_path = os.environ.get("LUKA_GATE_SOCK", DEFAULT_SOCK)

    if len(argv) >= 2:
        task_path = Path(argv[1])
    else:
        task_path = pick_latest_task(inbox)

    task = load_task_json(task_path)

    client = RPCClient(sock_path=sock_path)

    auth_resp: Any = {}
    run_resp: Optional[Dict[str, Any]] = None
    rejected = False
    reason = "ok"

    try:
        # 1) allowlist mapping (fast-fail)
        tool = map_action_to_tool(task.action)

        # 2) governance authorize (non-bypassable)
        auth_resp = authorize_or_raise(client, task)

        # 3) run tool
        run_resp = run_tool_zsh(tool, task)

        ok = (run_resp.get("exit_code") == 0)
        write_telemetry_latest(task, auth_resp, run_resp, rejected=False, reason="ok")
        append_beacon(task, ok=ok, event="task_committed", detail={"run": run_resp})
        print(json.dumps({"ok": ok, "task_id": task.task_id, "run": run_resp}, ensure_ascii=False))
        return 0 if ok else 1

    except Exception as e:
        rejected = True
        reason = str(e)

        # best-effort telemetry + ledger
        try:
            write_telemetry_latest(task, auth_resp, run_resp, rejected=True, reason=reason)
        except Exception:
            pass
        try:
            append_beacon(task, ok=False, event="task_rejected", detail={"error": reason})
        except Exception:
            pass

        print(json.dumps({"ok": False, "task_id": task.task_id, "error": reason}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
