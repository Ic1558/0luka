#!/usr/bin/env python3
"""
Zen Claim Gate - Evidence-Based System State Verifier

Purpose: Enforce "Evidence-first" verification before allowing Zen claims.
No more "Trust me, bro" - only hard evidence.

Usage:
    python3 zen_claim_gate.py --verify

Output: JSON evidence bundle with pass/fail verdict
"""

import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import hashlib

def _repo_root():
    import os, subprocess
    env = os.environ.get("LUKA_ROOT")
    if env:
        return env
    try:
        return subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    except Exception:
        return os.getcwd()



class ZenClaimGate:
    """Gatekeeper for Zen state claims - Evidence-based verification only"""
    
    def __init__(self):
        self.timestamp = datetime.now().isoformat()
        self.evidence = {}
        self.verdict = {"zen": False, "reasons": []}
        
    def run_command(self, cmd: str) -> Tuple[str, int]:
        """Run command and return (output, exit_code)"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout, result.returncode
        except Exception as e:
            return f"ERROR: {e}", 1
    
    def verify_registry_truth(self) -> bool:
        """Verification 1: LaunchAgent Registry"""
        print("🔍 [1/3] Verifying LaunchAgent Registry...")
        
        cmd = "launchctl list | awk '$3 ~ /^com\\.02luka\\./'"
        output, code = self.run_command(cmd)
        
        if code != 0:
            self.verdict["reasons"].append("Registry check failed")
            return False
        
        # Parse output
        lines = [l.strip() for l in output.split('\n') if l.strip()]
        
        # Count agents by exit code
        exit_127_126 = []
        healthy_running = []
        
        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                pid = parts[0]
                exit_code = parts[1]
                label = parts[2]
                
                if pid == "-" and exit_code in ["127", "126"]:
                    exit_127_126.append(label)
                elif pid != "-" and pid.isdigit():
                    healthy_running.append(label)
        
        self.evidence["registry"] = {
            "timestamp": self.timestamp,
            "total_agents": len(lines),
            "healthy_running": len(healthy_running),
            "exit_127_126": len(exit_127_126),
            "broken_agents": exit_127_126,
            "raw_output": output
        }
        
        if len(exit_127_126) > 0:
            self.verdict["reasons"].append(
                f"Found {len(exit_127_126)} broken agents (exit 127/126)"
            )
            return False
        
        print(f"  ✅ Registry clean: {len(healthy_running)} healthy, 0 broken")
        return True
    
    def verify_network_truth(self) -> bool:
        """Verification 2: Port 7001 Single Owner (Authoritative)"""
        print("🔍 [2/3] Verifying Network Ports (Authoritative)...")
        
        # Single authoritative command for ALL LISTEN ports
        cmd = "lsof -nP -iTCP -sTCP:LISTEN | sort"
        output, code = self.run_command(cmd)
        
        if code != 0:
            self.verdict["reasons"].append("Failed to get network port list")
            self.evidence["network"] = {
                "timestamp": self.timestamp,
                "status": "COMMAND_FAILED",
                "raw_output": output
            }
            return False
        
        # Parse all LISTEN ports
        all_ports = []
        port_7001_lines = []
        
        for line in output.split('\n'):
            if line.strip() and not line.startswith('COMMAND'):
                all_ports.append(line)
                if ':7001 (LISTEN)' in line:
                    port_7001_lines.append(line)
        
        # Check port 7001 specifically
        if len(port_7001_lines) == 0:
            self.verdict["reasons"].append("Port 7001 not in LISTEN state")
            self.evidence["network"] = {
                "timestamp": self.timestamp,
                "port_7001_status": "NOT_LISTENING",
                "all_listen_ports": len(all_ports),
                "raw_output": output
            }
            return False
        
        if len(port_7001_lines) > 1:
            self.verdict["reasons"].append(
                f"Port 7001 has {len(port_7001_lines)} owners (expected 1)"
            )
            self.evidence["network"] = {
                "timestamp": self.timestamp,
                "port_7001_status": "MULTIPLE_OWNERS",
                "owner_count": len(port_7001_lines),
                "all_listen_ports": len(all_ports),
                "raw_output": output
            }
            return False
        
        # Extract owner info from single 7001 line
        owner_line = port_7001_lines[0].split()
        owner_info = {
            "command": owner_line[0],
            "pid": owner_line[1],
            "user": owner_line[2]
        }
        
        self.evidence["network"] = {
            "timestamp": self.timestamp,
            "port_7001_status": "SINGLE_OWNER",
            "owner": owner_info,
            "all_listen_ports": len(all_ports),
            "raw_output": output  # Contains ALL ports for audit
        }
        
        print(f"  ✅ Port 7001: Single owner ({owner_info['command']} PID {owner_info['pid']})")
        print(f"  ℹ️  Total LISTEN ports: {len(all_ports)}")
        return True
    
    def verify_stability_truth(self, log_path: str = "${_repo_root()}/logs/mary_dispatcher.log") -> bool:
        """Verification 3: Log Growth Test (90 seconds)"""
        print("🔍 [3/3] Verifying Log Stability (90-second test)...")
        
        log_path = Path(log_path).expanduser()
        
        if not log_path.exists():
            print(f"  ⚠️  Log not found: {log_path} (assuming no noise)")
            self.evidence["stability"] = {
                "timestamp": self.timestamp,
                "log_path": str(log_path),
                "status": "LOG_NOT_FOUND",
                "verdict": "PASS"
            }
            return True
        
        # Read last 5 lines before
        cmd_before = f"tail -n 5 {log_path}"
        before, _ = self.run_command(cmd_before)
        
        print("  ⏱️  Waiting 90 seconds...")
        time.sleep(90)
        
        # Read last 5 lines after
        after, _ = self.run_command(cmd_before)
        
        # Compare
        growing = before != after
        
        self.evidence["stability"] = {
            "timestamp_start": self.timestamp,
            "timestamp_end": datetime.now().isoformat(),
            "log_path": str(log_path),
            "before": before,
            "after": after,
            "growing": growing
        }
        
        if growing:
            self.verdict["reasons"].append("Log still growing (new entries in 90s)")
            print("  ❌ Log still growing")
            return False
        
        print("  ✅ Log stable (no growth in 90s)")
        return True
    
    def verify_error_log_truth(self, manifest_path: str = "~/0luka/config/debt_manifest.json") -> bool:
        """Verification 4: Critical Error Logs Growth Test (Debt-Aware)"""
        print("🔍 [4/4] Verifying Error Logs (90-second test, debt-aware)...")
        
        # Load debt manifest
        manifest_path_expanded = Path(manifest_path).expanduser()
        known_debt = []
        if manifest_path_expanded.exists():
            try:
                with open(manifest_path_expanded, 'r') as f:
                    manifest = json.load(f)
                    known_debt = manifest.get("known_debt", [])
                    print(f"  📋 Loaded {len(known_debt)} known debt entries")
            except Exception as e:
                print(f"  ⚠️  Failed to load manifest: {e}")
        
        # Dynamic discovery: Find top 10 most recently modified error logs
        base_path = Path("${_repo_root()}").expanduser()
        
        if not base_path.exists():
            print("  ⚠️  Base path not found")
            self.evidence["error_logs"] = {
                "status": "BASE_PATH_NOT_FOUND",
                "verdict": "PASS"
            }
            return True
        
        # Find all .err.log and .stderr.log files
        error_logs = []
        for pattern in ["**/*.err.log", "**/*.stderr.log"]:
            error_logs.extend(base_path.glob(pattern))
        
        # Sort by modification time (most recent first), take top 10
        error_logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        top_logs = error_logs[:10]
        
        if not top_logs:
            print("  ℹ️  No error logs found")
            self.evidence["error_logs"] = {
                "status": "NO_LOGS_FOUND",
                "verdict": "PASS"
            }
            return True
        
        print(f"  📋 Discovered {len(error_logs)} error logs, monitoring top {len(top_logs)}")
        
        results = {}
        before_states = {}
        
        # Capture before state
        for log_path in top_logs:
            cmd = f"tail -n 3 {log_path}"
            before, _ = self.run_command(cmd)
            before_states[str(log_path)] = before
        
        print(f"  ⏱️  Monitoring {len(before_states)} error logs for 90 seconds...")
        time.sleep(90)
        
        # Capture after state and compare
        growing_logs = []
        known_debt_growing = []
        unknown_growing = []
        
        for log_path_str, before in before_states.items():
            cmd = f"tail -n 3 {log_path_str}"
            after, _ = self.run_command(cmd)
            
            if before != after:
                log_name = Path(log_path_str).name
                growing_logs.append(log_path_str)
                
                # Classify as known debt or unknown
                if log_name in known_debt:
                    known_debt_growing.append(log_name)
                    results[log_path_str] = {
                        "status": "GROWING",
                        "classification": "KNOWN_DEBT",
                        "before": before,
                        "after": after
                    }
                else:
                    unknown_growing.append(log_name)
                    results[log_path_str] = {
                        "status": "GROWING",
                        "classification": "UNKNOWN_NEW",
                        "before": before,
                        "after": after
                    }
            else:
                results[log_path_str] = {
                    "status": "STABLE"
                }
        
        self.evidence["error_logs"] = {
            "timestamp_start": self.timestamp,
            "timestamp_end": datetime.now().isoformat(),
            "total_discovered": len(error_logs),
            "monitored_count": len(before_states),
            "growing_count": len(growing_logs),
            "known_debt_count": len(known_debt_growing),
            "unknown_new_count": len(unknown_growing),
            "known_debt_list": known_debt_growing,
            "unknown_new_list": unknown_growing,
            "monitored_files": [str(p) for p in top_logs],
            "results": results
        }
        
        # Only fail if UNKNOWN logs are growing
        if unknown_growing:
            self.verdict["reasons"].append(
                f"{len(unknown_growing)} UNKNOWN error logs growing: {', '.join(unknown_growing)}"
            )
            print(f"  ❌ {len(unknown_growing)} UNKNOWN error logs growing")
            if known_debt_growing:
                print(f"  ℹ️  {len(known_debt_growing)} KNOWN_DEBT logs also growing (ignored)")
            return False
        
        if known_debt_growing:
            print(f"  ✅ All {len(before_states)} error logs stable (or KNOWN_DEBT)")
            print(f"  ℹ️  {len(known_debt_growing)} KNOWN_DEBT logs growing: {', '.join(known_debt_growing)}")
        else:
            print(f"  ✅ All {len(before_states)} error logs stable")
        
        return True
    
    def create_evidence_bundle(self) -> Dict:
        """Create canonical evidence bundle with hash"""
        bundle = {
            "claim": "TRUE_ZEN",
            "timestamp": self.timestamp,
            "verdict": self.verdict,
            "evidence": self.evidence
        }
        
        # Calculate hash
        bundle_str = json.dumps(bundle, sort_keys=True)
        bundle["hash"] = hashlib.sha256(bundle_str.encode()).hexdigest()[:16]
        
        return bundle
    
    def verify(self) -> Dict:
        """Run all verifications and return evidence bundle"""
        print("\n" + "="*60)
        print("🛡️  ZEN CLAIM GATE - Evidence-Based Verification")
        print("="*60 + "\n")
        
        # Run all 4 verifications
        registry_ok = self.verify_registry_truth()
        network_ok = self.verify_network_truth()
        stability_ok = self.verify_stability_truth()
        error_logs_ok = self.verify_error_log_truth()
        
        # Final verdict
        self.verdict["zen"] = registry_ok and network_ok and stability_ok and error_logs_ok
        
        # Create bundle
        bundle = self.create_evidence_bundle()
        
        # Print result
        print("\n" + "="*60)
        if bundle["verdict"]["zen"]:
            print("✅ VERDICT: TRUE ZEN STATE CONFIRMED")
            print("="*60)
            print(f"Evidence Hash: {bundle['hash']}")
        else:
            print("❌ VERDICT: NOT ZEN - Issues Found")
            print("="*60)
            print("Reasons:")
            for reason in bundle["verdict"]["reasons"]:
                print(f"  - {reason}")
        print()
        
        return bundle
    
    def save_bundle(self, bundle: Dict, output_dir: str = "~/0luka/artifacts/zen_claims"):
        """Save evidence bundle to file"""
        output_dir = Path(output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%y%m%d_%H%M%S")
        filename = f"zen_claim_{timestamp_str}_{bundle['hash']}.json"
        output_path = output_dir / filename
        
        with open(output_path, 'w') as f:
            json.dump(bundle, f, indent=2)
        
        print(f"📦 Evidence bundle saved: {output_path}")
        return output_path


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Zen Claim Gate - Evidence-Based Verifier")
    parser.add_argument("--verify", action="store_true", help="Run verification")
    parser.add_argument("--output", default="~/0luka/artifacts/zen_claims", help="Output directory")
    
    args = parser.parse_args()
    
    if args.verify:
        gate = ZenClaimGate()
        bundle = gate.verify()
        output_path = gate.save_bundle(bundle, args.output)
        
        # Exit with appropriate code
        exit(0 if bundle["verdict"]["zen"] else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
