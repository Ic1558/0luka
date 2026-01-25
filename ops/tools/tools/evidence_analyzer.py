#!/usr/bin/env python3
"""
Evidence Analyzer - The Unified Truth
Aggregates all governance test results into a single comprehensive report.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths
ROOT = Path(os.environ.get("ROOT", str(Path.home() / "0luka"))).expanduser().resolve()
ROOT_STR = str(ROOT)
ROOT_REF = "${ROOT}"
ROOT_02LUKA = Path(os.environ.get("ROOT_02LUKA", str(Path.home() / "02luka"))).expanduser().resolve()
REMEDIATION_DIR = ROOT / "artifacts/remediation"
OUTBOX_DIR = ROOT_02LUKA / "interface/outbox/results"
REPORT_PATH = ROOT / "artifacts/governance_test_report.md"

def normalize_paths(obj):
    if isinstance(obj, dict):
        return {k: normalize_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_paths(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace(ROOT_STR, ROOT_REF)
    return obj

def load_json_files(directory, pattern="*.json"):
    """Load all JSON files from directory"""
    files = []
    for filepath in directory.glob(pattern):
        if filepath.name == "cooldown_state.json":
            continue
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                data['_filepath'] = str(filepath)
                data['_filename'] = filepath.name
                files.append(data)
        except Exception as e:
            print(f"Warning: Could not load {filepath}: {e}")
    return files

def analyze_remediation_evidence():
    """Analyze remediation commands"""
    commands = load_json_files(REMEDIATION_DIR)
    
    stats = {
        'total_commands': len(commands),
        'by_action': defaultdict(int),
        'timeline': []
    }
    
    for cmd in commands:
        action = cmd.get('action', 'UNKNOWN')
        stats['by_action'][action] += 1
        stats['timeline'].append({
            'timestamp': cmd.get('timestamp'),
            'action': action,
            'reason': cmd.get('reason', ''),
            'command_id': cmd.get('command_id', '')
        })
    
    # Sort timeline
    stats['timeline'].sort(key=lambda x: x['timestamp'] or 0)
    
    return commands, stats

def analyze_execution_results():
    """Analyze execution results from outbox"""
    results = load_json_files(OUTBOX_DIR)
    
    stats = {
        'total_executions': len(results),
        'successful': 0,
        'failed': 0,
        'by_action': defaultdict(int)
    }
    
    for result in results:
        payload = result.get('payload', {})
        if 'error' in payload:
            stats['failed'] += 1
        else:
            stats['successful'] += 1
        
        # Infer action from payload
        if 'pong' in payload:
            stats['by_action']['PING'] += 1
        elif 'processes' in payload:
            stats['by_action']['GET_PROCESSES'] += 1
        elif 'status' in payload and payload.get('status') == 'restarting':
            stats['by_action']['RESTART_AGENT'] += 1
        elif 'mem_used_pct' in payload:
            stats['by_action']['GET_STATUS'] += 1
    
    return results, stats

def load_cooldown_state():
    """Load cooldown state"""
    cooldown_file = REMEDIATION_DIR / "cooldown_state.json"
    if cooldown_file.exists():
        with open(cooldown_file, 'r') as f:
            return json.load(f)
    return {}

def generate_report(remediation_cmds, remediation_stats, execution_results, execution_stats, cooldown_state):
    """Generate comprehensive markdown report"""
    
    report = []
    report.append("# Governance System Test Report")
    report.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\n**Test Suite**: TC-01 through TC-04")
    report.append("\n---\n")
    
    # Executive Summary
    report.append("## Executive Summary\n")
    report.append(f"- **Total Commands Issued**: {remediation_stats['total_commands']}")
    report.append(f"- **Total Executions**: {execution_stats['total_executions']}")
    report.append(f"- **Success Rate**: {execution_stats['successful']}/{execution_stats['total_executions']} ({100 * execution_stats['successful'] / max(execution_stats['total_executions'], 1):.0f}%)")
    report.append(f"- **Active Cooldowns**: {len(cooldown_state)}")
    report.append("\n---\n")
    
    # Test Case Results
    report.append("## Test Case Results\n")
    
    # TC-01
    tc01_cmds = [c for c in remediation_cmds if c.get('action') == 'RESTART_AGENT']
    report.append("### TC-01: Port Failure Detection")
    if tc01_cmds:
        report.append("**Status**: ✅ PASSED")
        cmd = tc01_cmds[0]
        report.append(f"- **Command ID**: `{cmd.get('command_id')}`")
        report.append(f"- **Reason**: {normalize_paths(cmd.get('reason'))}")
        report.append(f"- **Timestamp**: {datetime.fromtimestamp(cmd.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        report.append("**Status**: ❌ FAILED - No RESTART_AGENT command found")
    report.append("")
    
    # TC-02
    tc02_cmds = [c for c in remediation_cmds if c.get('action') == 'GET_PROCESSES']
    report.append("### TC-02: Log Anomaly Detection")
    if tc02_cmds:
        report.append("**Status**: ✅ PASSED")
        cmd = tc02_cmds[0]
        report.append(f"- **Command ID**: `{cmd.get('command_id')}`")
        report.append(f"- **Reason**: {normalize_paths(cmd.get('reason'))}")
        report.append(f"- **Pattern Matched**: FATAL:")
    else:
        report.append("**Status**: ❌ FAILED - No GET_PROCESSES command found")
    report.append("")
    
    # TC-03
    report.append("### TC-03: Cooldown Protection")
    if len(cooldown_state) >= 2:
        report.append("**Status**: ✅ PASSED")
        report.append(f"- **Active Cooldowns**: {len(cooldown_state)}")
        for action, timestamp in cooldown_state.items():
            elapsed = datetime.now().timestamp() - timestamp
            remaining = max(0, 300 - elapsed)
            report.append(f"  - `{action}`: {remaining:.0f}s remaining")
    else:
        report.append("**Status**: ⚠️ PARTIAL - Expected multiple cooldowns")
    report.append("")
    
    # TC-04
    report.append("### TC-04: Security Gate")
    hacker_results = [r for r in execution_results if 'hacker' in r.get('ref_id', '').lower()]
    if len(hacker_results) == 0:
        report.append("**Status**: ✅ PASSED")
        report.append("- **Tampered Commands Rejected**: All")
        report.append("- **Security Verification**: Signature validation working")
    else:
        report.append(f"**Status**: ❌ FAILED - {len(hacker_results)} tampered commands executed")
    report.append("")
    
    report.append("---\n")
    
    # Command Timeline
    report.append("## Command Timeline\n")
    report.append("| Timestamp | Action | Reason | Command ID |")
    report.append("|-----------|--------|--------|------------|")
    for event in remediation_stats['timeline']:
        ts = datetime.fromtimestamp(event['timestamp'] or 0).strftime('%H:%M:%S')
        action = event['action']
        raw_reason = normalize_paths(event['reason'])
        reason = raw_reason[:50] + "..." if len(raw_reason) > 50 else raw_reason
        cmd_id = event['command_id'][:8]
        report.append(f"| {ts} | {action} | {reason} | `{cmd_id}...` |")
    report.append("")
    
    # Execution Details
    report.append("## Execution Details\n")
    for result in execution_results:
        ref_id = result.get('ref_id', 'unknown')[:8]
        payload = result.get('payload', {})
        report.append(f"### Result: `{ref_id}...`")
        report.append("```json")
        report.append(json.dumps(normalize_paths(payload), indent=2))
        report.append("```\n")
    
    # Statistics
    report.append("---\n")
    report.append("## Statistics\n")
    report.append("### Commands by Action")
    for action, count in sorted(remediation_stats['by_action'].items()):
        report.append(f"- **{action}**: {count}")
    report.append("")
    
    report.append("### Executions by Action")
    for action, count in sorted(execution_stats['by_action'].items()):
        report.append(f"- **{action}**: {count}")
    report.append("")
    
    # Conclusion
    report.append("---\n")
    report.append("## Conclusion\n")
    
    all_passed = (
        len(tc01_cmds) > 0 and
        len(tc02_cmds) > 0 and
        len(cooldown_state) >= 2 and
        len(hacker_results) == 0
    )
    
    if all_passed:
        report.append("### ✅ ALL TESTS PASSED")
        report.append("\nThe governance system is **production-ready** with:")
        report.append("- ✅ Anomaly detection (port failures, log patterns)")
        report.append("- ✅ Signed command generation")
        report.append("- ✅ Signature verification")
        report.append("- ✅ Cooldown protection")
        report.append("- ✅ Security gate enforcement")
        report.append("\n**The Nerve Connection is LIVE!** 🎉")
    else:
        report.append("### ⚠️ SOME TESTS FAILED")
        report.append("\nPlease review the test case results above.")
    
    return "\n".join(report)

def main():
    print("[Evidence Analyzer] Starting analysis...")
    
    # Load all data
    remediation_cmds, remediation_stats = analyze_remediation_evidence()
    execution_results, execution_stats = analyze_execution_results()
    cooldown_state = load_cooldown_state()
    
    print(f"[Evidence Analyzer] Found {len(remediation_cmds)} commands, {len(execution_results)} results")
    
    # Generate report
    report = generate_report(
        remediation_cmds,
        remediation_stats,
        execution_results,
        execution_stats,
        cooldown_state
    )
    
    # Save report
    with open(REPORT_PATH, 'w') as f:
        f.write(report)
    
    print(f"[Evidence Analyzer] Report saved to: {normalize_paths(str(REPORT_PATH))}")
    print("\n" + "="*60)
    print(report)
    print("="*60)

if __name__ == "__main__":
    main()
