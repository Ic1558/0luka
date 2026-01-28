#!/usr/bin/env python3
import sys
import json
import subprocess
import time
import datetime
from pathlib import Path
from typing import Optional, List

# Ensure we use the .venv if running directly (optional safeguard)
try:
    from mcp.server.fastmcp import FastMCP, Context, Image
except ImportError:
    print("Error: 'mcp' module not found. Please run within the .venv where mcp is installed.", file=sys.stderr)
    sys.exit(1)

# Initialize MCP Server
mcp = FastMCP("0luka")

# Paths
ROOT = Path(__file__).resolve().parent.parent.parent
SESSION_MD = ROOT / "g/session/SESSION_STATE.md"
BEACON_LOG = ROOT / "observability/stl/ledger/global_beacon.jsonl"
BRIDGE_EMIT = ROOT / "system/bin/bridge-emit"
BRIDGE_DISPATCHER = ROOT / "core_brain/ops/governance/bridge_dispatcher.py"
INTERFACE_PLANS = ROOT / "interface/plans"
INTERFACE_INBOX = ROOT / "interface/inbox"
INTERFACE_WIP = ROOT / "interface/wip"

# Import Log Rotator
sys.path.append(str(ROOT / "core_brain/ops"))
try:
    from log_rotator import LogRotator
except ImportError:
    LogRotator = None

# --- Core Tools ---

@mcp.tool()
def get_session_context() -> str:
    """Read the current SESSION_STATE.md to understand active context."""
    if not SESSION_MD.exists():
        return "SESSION_STATE.md not found."
    return SESSION_MD.read_text()

@mcp.tool()
def read_bridge_logs(lines: int = 50) -> List[dict]:
    """Read recent bridge activity logs (Global Beacon)."""
    if not BEACON_LOG.exists():
        return [{"error": "Beacon log not found"}]
    
    logs = []
    try:
        with open(BEACON_LOG, 'r') as f:
            all_lines = f.readlines()
            last_n = all_lines[-lines:]
            for line in last_n:
                try:
                    logs.append(json.loads(line))
                except:
                    continue
    except Exception as e:
        return [{"error": f"Failed to read logs: {e}"}]
    return logs

@mcp.tool()
def emit_bridge_task(intent: str, payload: str) -> str:
    """
    Submit a task to the 0luka Bridge.
    Args:
        intent: The intent name (e.g., 'plan', 'verify').
        payload: JSON string payload for the task.
    """
    try:
        json.loads(payload)
        cmd = [str(BRIDGE_EMIT), "--origin", "gemini-mcp", "--intent", intent, "--payload", payload]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        if result.returncode != 0:
            return f"Error emitting task: {result.stderr}"
        subprocess.Popen(["python3", str(BRIDGE_DISPATCHER)], cwd=str(ROOT))
        return f"Task emitted successfully. Output: {result.stdout.strip()}"
    except json.JSONDecodeError:
        return "Error: Payload must be a valid JSON string."
    except Exception as e:
        return f"Internal Error: {e}"

@mcp.tool()
def list_agents() -> str:
    """List 0luka Agents and their status."""
    return """
    Active Agents:
    - Liam (Planning): Ready
    - Lisa (Execution): Ready
    - Codex (Verification): Ready
    - Bridge Dispatcher: Active
    """

# --- Power Tools (Phase 3.5) ---

@mcp.tool()
def system_remedy(target: str) -> str:
    """
    Autonomously fix system issues.
    Args:
        target: The target to fix (e.g., 'port:7001').
    """
    if target == "port:7001":
        try:
            # Find PID using lsof
            lsof_cmd = ["lsof", "-t", "-i:7001"]
            pid_res = subprocess.run(lsof_cmd, capture_output=True, text=True)
            pids = pid_res.stdout.strip().split('\n')
            pids = [p for p in pids if p]
            
            if not pids:
                return "✅ Port 7001 is already free."
            
            # Kill PIDs
            killed = []
            for pid in pids:
                subprocess.run(["kill", "-9", pid])
                killed.append(pid)
            
            return f"✅ Remediation Complete: Killed interfering processes (PIDs: {', '.join(killed)}) on Port 7001."
        except Exception as e:
            return f"❌ Remediation Failed: {e}"
    
    return f"❌ Unknown remedy target: {target}"

@mcp.tool()
def inspect_interface() -> str:
    """
    Observer Tool: Inspect the state of Interface folders (Plans, Inbox, WIP).
    Returns a summary of pending work.
    """
    summary = ["## Interface Inspector Snapshot"]
    
    def scan(path, name):
        if not path.exists():
            summary.append(f"- {name}: [Missing Directory]")
            return
        files = list(path.glob("*"))
        if not files:
            summary.append(f"- {name}: (Empty)")
        else:
            summary.append(f"- {name}: {len(files)} items")
            for f in files[:5]: # Top 5
                summary.append(f"  - {f.name}")
    
    scan(INTERFACE_PLANS, "Plans (Liam)")
    scan(INTERFACE_INBOX, "Inbox (Bridge)")
    scan(INTERFACE_WIP, "WIP (Lisa)")
    
    return "\n".join(summary)

@mcp.tool()
def distill_notebook_context(date: Optional[str] = None) -> str:
    """
    Knowledge Synthesizer: Summarize logs into a NotebookLM-ready journal entry.
    Args:
        date: Optional date filter (YYYY-MM-DD). Defaults to today.
    """
    if not date:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Simple extraction from Global Beacon
    entries = read_bridge_logs(lines=200) # Get decent chunk
    
    journal = [f"# Daily Journal: {date}", "## Key Events"]
    
    count = 0
    for entry in entries:
        ts = entry.get("timestamp", "")
        if format_timestamp(ts).startswith(date):
            intent = entry.get("intent", "unknown")
            if intent in ["plan", "verify", "run"]:
                journal.append(f"- **{intent.upper()}**: {json.dumps(entry.get('payload', {}))}")
                count += 1
    
    if count == 0:
        journal.append("(No significant events logged for today)")
    
    return "\n".join(journal)

def format_timestamp(iso_str):
    # Basic helper, assumes ISO string "2026-01-29T..."
    return iso_str.split("T")[0]

@mcp.tool()
def rotate_logs(confirm: bool = False) -> str:
    """
    Perform Log Rotation / Correction Hygiene.
    Args:
        confirm: Set to True to actually delete files. False (default) is Dry Run.
    """
    if not LogRotator:
        return "❌ LogRotator module not found or failed to load."
    
    rotator = LogRotator(str(ROOT))
    report = rotator.rotate(dry_run=not confirm)
    return "\n".join(report)

if __name__ == "__main__":
    mcp.run()
