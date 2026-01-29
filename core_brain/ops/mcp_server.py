#!/usr/bin/env python3
import sys
import json
import subprocess
import time
import datetime
import re
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

# --- Power Tools (Phase 3.5) ---

def _log_remedy(msg: str):
    ts = datetime.datetime.now().isoformat()
    log_file = ROOT / "observability/logs/heartbeat.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(f"[{ts}] [REMEDY] {msg}\n")

@mcp.tool()
def remediate_system(target: str) -> str:
    """
    Autonomously fix system issues.
    Args:
        target: The target to fix (e.g., 'port:7001', 'module:opal_api').
    """
    _log_remedy(f"Attempting remedy for target: {target}")
    
    if target.startswith("port:"):
        try:
            port = target.split(":")[1]
            # Find PID using lsof
            lsof_cmd = ["lsof", "-t", f"-i:{port}"]
            pid_res = subprocess.run(lsof_cmd, capture_output=True, text=True)
            pids = pid_res.stdout.strip().split('\n')
            pids = [p for p in pids if p]
            
            if not pids:
                return f"✅ Port {port} is already free."
            
            # Safety Check: Ensure we aren't killing critical system processes (PID 1 or very low)
            to_kill = []
            for pid in pids:
                if int(pid) < 100:
                    _log_remedy(f"SKIP cleanup: PID {pid} is a system process.")
                    continue
                to_kill.append(pid)
            
            if not to_kill:
                 return f"⚠️ No safe processes found to kill on port {port}."

            for pid in to_kill:
                subprocess.run(["kill", "-9", pid])
                _log_remedy(f"Killed PID {pid} on {target}")
            
            return f"✅ Remediation Complete: Killed interfering processes ({', '.join(to_kill)}) on {target}."
        except Exception as e:
            _log_remedy(f"ERROR on {target}: {e}")
            return f"❌ Remediation Failed: {e}"

    if target.startswith("module:"):
        module_name = target.split(":")[1]
        try:
            modulectl = ROOT / "core_brain/ops/modulectl.py"
            # Attempt to enable/kickstart the module
            cmd = ["python3", str(modulectl), "enable", module_name]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                _log_remedy(f"Successfully enabled module: {module_name}")
                return f"✅ Module '{module_name}' remediation successful: {res.stdout.strip()}"
            else:
                _log_remedy(f"Failed to enable module {module_name}: {res.stderr}")
                return f"❌ Module '{module_name}' remediation failed: {res.stderr.strip()}"
        except Exception as e:
            _log_remedy(f"ERROR on {target}: {e}")
            return f"❌ Remediation Failed: {e}"
    
    return f"❌ Unknown remedy target format: {target}. Use 'port:NNNN' or 'module:NAME'."

@mcp.tool()
def analyze_session_health() -> str:
    """
    Synthesize session context and system health into a status report.
    Returns: A markdown report of current goals, recent errors, and system drift.
    """
    summary = ["# 0luka Session Health Report", ""]
    
    # 1. State from SESSION_STATE.md
    if SESSION_MD.exists():
        state_txt = SESSION_MD.read_text()
        m = re.search(r"## What changed\n(.*?)\n\n", state_txt, re.S)
        if m:
            summary.append("## Active Goals / Context")
            summary.append(m.group(1).strip())
            summary.append("")

    # 2. System Drift (modulectl check)
    try:
        modulectl = ROOT / "core_brain/ops/modulectl.py"
        res = subprocess.run(["python3", str(modulectl), "status", "all"], capture_output=True, text=True)
        # Scan for common failure strings
        failures = []
        for line in res.stdout.splitlines():
            if "NOT LOADED" in line or "not listening" in line:
                failures.append(line)
        
        if failures:
            summary.append("## ⚠️ System Drift Detected")
            for f in failures:
                summary.append(f"- {f}")
        else:
            summary.append("## ✅ System Normal")
            summary.append("All core modules are reported running and ports are healthy.")
    except Exception as e:
        summary.append(f"## ❌ Health Check Error: {e}")

    summary.append(f"\n*Report generated at {datetime.datetime.now().isoformat()}*")
    return "\n".join(summary)

@mcp.tool()
def prepare_notebook_bundle() -> str:
    """
    Package session state, beacon logs, and remediation logs for external analysis.
    Returns: Absolute path to the generated bundle.
    """
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    bundle_dir = ROOT / "observability/artifacts/bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_file = bundle_dir / f"session_bundle_{ts}.md"
    
    bundle_content = [f"# 0luka Session Bundle: {ts}", ""]
    
    # Add Session State
    if SESSION_MD.exists():
        bundle_content.append("## 📄 SESSION_STATE.md")
        bundle_content.append("```markdown")
        bundle_content.append(SESSION_MD.read_text())
        bundle_content.append("```\n")
    
    # Add Remediation Logs (Heartbeat)
    hb_log = ROOT / "observability/logs/heartbeat.log"
    if hb_log.exists():
        bundle_content.append("## 💓 Heartbeat / Remedy Logs")
        bundle_content.append("```text")
        # Tail 100 lines
        with open(hb_log, "r") as f:
            lines = f.readlines()[-100:]
            bundle_content.extend([l.strip() for l in lines])
        bundle_content.append("```\n")
    
    # Add Recent Beacon Activity
    if BEACON_LOG.exists():
        bundle_content.append("## 📡 Recent Activity (Beacon)")
        bundle_content.append("```jsonl")
        with open(BEACON_LOG, "r") as f:
            lines = f.readlines()[-50:]
            bundle_content.extend([l.strip() for l in lines])
        bundle_content.append("```\n")

    bundle_file.write_text("\n".join(bundle_content), encoding="utf-8")
    return f"✅ Bundle created: {bundle_file}"

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
