# Judicial Reality Audit

- Generated: 2026-01-25T03:05:58+07:00
- Root: /Users/icmini/0luka

## 0) Existence + Layout
```text
total 8
drwxr-xr-x   13 icmini  staff    416 Jan 25 00:52 .
drwxr-xr-x@ 405 icmini  staff  12960 Jan 25 02:57 ..
drwxr-xr-x    5 icmini  staff    160 Jan 24 00:18 .0luka
drwxr-xr-x@  15 icmini  staff    480 Jan 25 03:02 .git
-rw-r--r--@   1 icmini  staff    135 Jan 24 01:03 .gitignore
drwxr-xr-x@   8 icmini  staff    256 Jan 25 02:55 .opencode
drwxr-xr-x@   3 icmini  staff     96 Jan 24 01:21 .openwork
drwxr-xr-x    2 icmini  staff     64 Jan 23 12:16 .tmp
drwxr-xr-x@   7 icmini  staff    224 Jan 24 02:56 .venv
drwxr-xr-x@   9 icmini  staff    288 Jan 24 06:13 core
drwxr-xr-x@   9 icmini  staff    288 Jan 25 03:04 observability
drwxr-xr-x@   4 icmini  staff    128 Jan 24 06:13 ops
drwxr-xr-x@   9 icmini  staff    288 Jan 25 02:29 runtime
```

## 1) Key Paths Present?
```text
OK  /Users/icmini/0luka/runtime/sock
OK  /Users/icmini/0luka/runtime/sock/gate_runner.sock
OK  /Users/icmini/0luka/core/governance/ontology.yaml
OK  /Users/icmini/0luka/observability/stl/evidence
OK  /Users/icmini/0luka/observability/stl/tasks/open
OK  /Users/icmini/0luka/ops/governance
OK  /Users/icmini/0luka/ops/governance/handlers
```

## 2) Socket Reality (owner/perm + listener)
```text
srw-rw----@ 1 icmini  staff  0 Jan 25 02:40 /Users/icmini/0luka/runtime/sock/gate_runner.sock
Python    51516 icmini    3u  unix 0xda44c075ee55d7b4      0t0      /Users/icmini/0luka/runtime/sock/gate_runner.sock
```

## 3) Protocol Framing Risk Scan
- Searching for recv(4096), json.loads(data), single-shot reads
```text
/Users/icmini/0luka/ops/governance/judicial_reality_audit.zsh:56:  echo "- Searching for recv(4096), json.loads(data), single-shot reads"
/Users/icmini/0luka/ops/governance/judicial_reality_audit.zsh:58:  # Fixed regex: searching for recv(4096) or json.loads(data)
/Users/icmini/0luka/ops/governance/gate_runnerd.py:126:            data = conn.recv(4096).decode()
/Users/icmini/0luka/ops/governance/gate_runnerd.py:128:            req = json.loads(data)
/Users/icmini/0luka/ops/governance/gate_runnerd.py:142:            conn.sendall(json.dumps(resp).encode())
/Users/icmini/0luka/ops/governance/gate_runnerd.py:145:            conn.sendall(json.dumps({"error": str(e)}).encode())
/Users/icmini/0luka/observability/audit/260125_030558_judicial_reality_audit.md:42:- Searching for recv(4096), json.loads(data), single-shot reads
/Users/icmini/0luka/observability/audit/260125_030457_judicial_reality_audit.md:42:- Searching for recv(4096), json.loads(data), single-shot reads
/Users/icmini/0luka/ops/governance/rpc_client.py:20:            client.sendall(json.dumps(payload).encode())
/Users/icmini/0luka/ops/governance/rpc_client.py:22:            response = client.recv(4096).decode()
/Users/icmini/0luka/observability/audit/260125_030527_judicial_reality_audit.md:42:- Searching for recv(4096), json.loads(data), single-shot reads
/Users/icmini/0luka/observability/audit/260125_030504_judicial_reality_audit.md:42:- Searching for recv(4096), json.loads(data), single-shot reads
```

## 4) Direct Import / Bypass Scan
- Looking for direct imports/calls that bypass socket
```text
/Users/icmini/0luka/ops/governance/judicial_reality_audit.zsh:66:  (command -v rg >/dev/null && rg -n "GateRunnerDaemon|gate_runnerd|import\\s+.*gate_runner|SOCK_PATH|AF_UNIX" "$ROOT" || echo "rg not found") | sed -n '1,200p'
/Users/icmini/0luka/ops/governance/rpc_client.py:14:            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
/Users/icmini/0luka/ops/governance/gate_runnerd.py:9:class GateRunnerDaemon:
/Users/icmini/0luka/ops/governance/gate_runnerd.py:12:    SOCK_PATH = ROOT / "runtime/sock/gate_runner.sock"
/Users/icmini/0luka/ops/governance/gate_runnerd.py:149:        if self.SOCK_PATH.exists(): self.SOCK_PATH.unlink()
/Users/icmini/0luka/ops/governance/gate_runnerd.py:150:        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
/Users/icmini/0luka/ops/governance/gate_runnerd.py:151:        server.bind(str(self.SOCK_PATH))
/Users/icmini/0luka/ops/governance/gate_runnerd.py:153:        os.chmod(self.SOCK_PATH, 0o660)
/Users/icmini/0luka/ops/governance/gate_runnerd.py:159:    daemon = GateRunnerDaemon()
/Users/icmini/0luka/observability/audit/260125_030558_judicial_reality_audit.md:46:/Users/icmini/0luka/ops/governance/gate_runnerd.py:126:            data = conn.recv(4096).decode()
/Users/icmini/0luka/observability/audit/260125_030558_judicial_reality_audit.md:47:/Users/icmini/0luka/ops/governance/gate_runnerd.py:128:            req = json.loads(data)
/Users/icmini/0luka/observability/audit/260125_030558_judicial_reality_audit.md:48:/Users/icmini/0luka/ops/governance/gate_runnerd.py:142:            conn.sendall(json.dumps(resp).encode())
/Users/icmini/0luka/observability/audit/260125_030558_judicial_reality_audit.md:49:/Users/icmini/0luka/ops/governance/gate_runnerd.py:145:            conn.sendall(json.dumps({"error": str(e)}).encode())
/Users/icmini/0luka/observability/artifacts/snapshots/260125_024527_snapshot.md:84:#### gate_runnerd_v3.log (last 10 lines)
/Users/icmini/0luka/observability/artifacts/snapshots/260125_024637_snapshot.md:54:#### gate_runnerd_v3.log (last 10 lines)
/Users/icmini/0luka/observability/artifacts/snapshots/260125_025716_snapshot.md:54:#### gate_runnerd_v3.log (last 10 lines)
/Users/icmini/0luka/observability/artifacts/snapshots/260125_025158_snapshot.md:54:#### gate_runnerd_v3.log (last 10 lines)
/Users/icmini/0luka/observability/artifacts/snapshots/260125_030234_snapshot.md:54:#### gate_runnerd_v3.log (last 10 lines)
/Users/icmini/0luka/observability/artifacts/snapshots/260125_024128_snapshot.md:40:#### gate_runnerd_v3.log (last 10 lines)
```

## 5) Temporal Law Check (IDCounter / datetime usage)
```text
/Users/icmini/0luka/ops/governance/drift_monitor.py:6:from datetime import datetime, timezone
/Users/icmini/0luka/ops/governance/drift_monitor.py:25:        "ts_iso": datetime.now().astimezone().isoformat(),
/Users/icmini/0luka/ops/governance/drift_monitor.py:52:        time.sleep(30)
/Users/icmini/0luka/ops/governance/judicial_reality_audit.zsh:70:  echo "## 5) Temporal Law Check (IDCounter / datetime usage)"
/Users/icmini/0luka/ops/governance/judicial_reality_audit.zsh:72:  (command -v rg >/dev/null && rg -n "class\\s+IDCounter|IDCounter\\(|datetime|time\\." "$ROOT" || echo "rg not found") | sed -n '1,200p'
/Users/icmini/0luka/ops/governance/foundation_decommission.sh:36:from datetime import datetime
/Users/icmini/0luka/ops/governance/foundation_decommission.sh:64:            json.dump({"task_id": task_id, "ts": datetime.utcnow().isoformat(), "results": results}, f, indent=2)
/Users/icmini/0luka/ops/governance/gate_runner.py:3:from datetime import datetime
/Users/icmini/0luka/ops/governance/gate_runner.py:73:        now = datetime.now()
/Users/icmini/0luka/ops/governance/id_counter.py:3:from datetime import datetime
/Users/icmini/0luka/ops/governance/id_counter.py:5:class IDCounter:
/Users/icmini/0luka/ops/governance/id_counter.py:13:        now = datetime.now()
/Users/icmini/0luka/ops/governance/id_counter.py:36:    counter = IDCounter()
/Users/icmini/0luka/ops/governance/gate_runnerd.py:24:        self.counter = IDCounter()
/Users/icmini/0luka/ops/tools/tools/evidence_analyzer.py:9:from datetime import datetime
/Users/icmini/0luka/ops/tools/tools/evidence_analyzer.py:101:    report.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
/Users/icmini/0luka/ops/tools/tools/evidence_analyzer.py:124:        report.append(f"- **Timestamp**: {datetime.fromtimestamp(cmd.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')}")
/Users/icmini/0luka/ops/tools/tools/evidence_analyzer.py:148:            elapsed = datetime.now().timestamp() - timestamp
/Users/icmini/0luka/ops/tools/tools/evidence_analyzer.py:173:        ts = datetime.fromtimestamp(event['timestamp'] or 0).strftime('%H:%M:%S')
/Users/icmini/0luka/ops/tools/tools/remediator.py:13:from datetime import datetime, timedelta
/Users/icmini/0luka/ops/tools/tools/remediator.py:50:        elapsed = time.time() - last_trigger
/Users/icmini/0luka/ops/tools/tools/remediator.py:64:    state[action] = time.time()
/Users/icmini/0luka/ops/tools/tools/remediator.py:77:        "timestamp": time.time(),
/Users/icmini/0luka/ops/tools/tools/remediator.py:89:    evidence_file = REMEDIATION_DIR / f"{datetime.now().strftime('%y%m%d_%H%M%S')}_{action}.json"
/Users/icmini/0luka/ops/tools/tools/remediator.py:96:            "timestamp": time.time()
/Users/icmini/0luka/ops/tools/tools/canary_alert.py:23:from datetime import datetime
/Users/icmini/0luka/ops/tools/tools/canary_alert.py:51:    now = time.time()
/Users/icmini/0luka/ops/tools/tools/canary_alert.py:90:                if time.time() - latest_cmd.get("timestamp", 0) > 60:
/Users/icmini/0luka/ops/tools/tools/canary_alert.py:118:    timestamp = datetime.now().strftime("%H:%M:%S")
/Users/icmini/0luka/ops/tools/tools/canary_alert.py:139:    current_time = time.time()
/Users/icmini/0luka/ops/tools/tools/zen_claim_gate.py:17:from datetime import datetime
/Users/icmini/0luka/ops/tools/tools/zen_claim_gate.py:27:        self.timestamp = datetime.now().isoformat()
/Users/icmini/0luka/ops/tools/tools/zen_claim_gate.py:185:        time.sleep(90)
/Users/icmini/0luka/ops/tools/tools/zen_claim_gate.py:195:            "timestamp_end": datetime.now().isoformat(),
/Users/icmini/0luka/ops/tools/tools/zen_claim_gate.py:266:        time.sleep(90)
/Users/icmini/0luka/ops/tools/tools/zen_claim_gate.py:305:            "timestamp_end": datetime.now().isoformat(),
/Users/icmini/0luka/ops/tools/tools/zen_claim_gate.py:389:        timestamp_str = datetime.now().strftime("%y%m%d_%H%M%S")
/Users/icmini/0luka/observability/audit/260125_030558_judicial_reality_audit.md:82:## 5) Temporal Law Check (IDCounter / datetime usage)
/Users/icmini/0luka/runtime/mcp/mcp_server_0luka.py:16:counter = IDCounter()
/Users/icmini/0luka/runtime/mcp/mcp_server_0luka.py:76:    # 2. Canonical Identity Generation (tk_key Law) - No datetime
/Users/icmini/0luka/runtime/apps/opal_api/opal_api_server.py:18:from datetime import datetime
/Users/icmini/0luka/runtime/apps/opal_api/opal_api_server.py:102:        timestamp=datetime.now().isoformat(),
/Users/icmini/0luka/runtime/apps/opal_api/opal_api_server.py:127:    data["api_timestamp"] = datetime.now().isoformat()
/Users/icmini/0luka/runtime/apps/opal_api/opal_api_server.py:139:            "timestamp": datetime.now().isoformat(),
/Users/icmini/0luka/runtime/apps/opal_api/opal_api_server.py:147:        "timestamp": data.get("timestamp", datetime.now().isoformat()),
/Users/icmini/0luka/runtime/apps/opal_api/opal_api_server.py:148:        "api_timestamp": datetime.now().isoformat(),
/Users/icmini/0luka/runtime/apps/opal_api/opal_api_server.py:183:    data["api_timestamp"] = datetime.now().isoformat()
```

## 6) Evidence Store + Chain Anchoring
```text
[evidence dir] /Users/icmini/0luka/observability/stl/evidence
/Users/icmini/0luka/observability/stl/evidence/260125_021457_task_legacy_decom_7203b542.yaml/260125_021458_attn_task_e7d929d4.json
/Users/icmini/0luka/observability/stl/evidence/260125_015951_task_zen_baseline_0860abbc.yaml/260125_020019_attn_task_ee7c9ca9.json
/Users/icmini/0luka/observability/stl/evidence/260125_015351_task_001_behavior_baseline_4c310343.yaml/260125_000001_attn_task_3e82296e.json
/Users/icmini/0luka/observability/stl/evidence/260125_015351_task_001_behavior_baseline_4c310343.yaml/260125_015412_attn_task_e37b6282.json
/Users/icmini/0luka/observability/stl/evidence/260125_020316_task_final_claim__2b9005e6.yaml/260125_020317_attn_task_4a6f9b9a.json
```

## 7) Anti-symlink / TOCTOU Surface
- Checking handlers and evidence paths for symlinks
```text
== /Users/icmini/0luka/ops/governance ==
== /Users/icmini/0luka/ops/governance/handlers ==
== /Users/icmini/0luka/observability/stl ==
== /Users/icmini/0luka/runtime ==
/Users/icmini/0luka/runtime/venv/opal/bin/𝜋thon
/Users/icmini/0luka/runtime/venv/opal/bin/python3
/Users/icmini/0luka/runtime/venv/opal/bin/python
/Users/icmini/0luka/runtime/venv/opal/bin/python3.14
```

## 8) Ontology Authority (is it still policy root?)
```text
[ontology] /Users/icmini/0luka/core/governance/ontology.yaml
-rw-r--r--@ 1 icmini  staff  1245 Jan 25 02:14 /Users/icmini/0luka/core/governance/ontology.yaml
version: "0.2"
status: "AUTHORITATIVE"
entities:
  opal-api:
    class: "core-service"
    identity: { port: 7001, process_name: "uvicorn", binary_contains: "runtime/venv/opal" }
  heartbeat-service:
    class: "observability-agent"
    identity: { launchd_label: "com.0luka.heartbeat" }
  legacy-bridge:
    class: "transition-group"
    members: ["mary_dispatcher", "clc_bridge", "shell_watcher"]
    policy: "DEPRECATED_STRICT"
    enforcement: "BLOCK_NEW_SPAWNS"

invariants:
  strict_root:
    allow: ["core", "runtime", "ops", "observability", ".git", ".0luka", ".opencode", ".openwork"]
    remediation: "auto-quarantine"
  canonical_naming:
    pattern: "^[0-9]{6}_[0-9]{6}_.*"
    enforced_by: "gate.naming.canonical"

actions:
  service_restart:
    id: "action.service.restart"
    pre_gates: ["gate.proc.purity"]
    post_gates: ["gate.net.port", "gate.proc.purity"]
    handler: "ops/governance/handlers/service_restart.zsh"
  system_audit:
    id: "action.system.audit"
    handler: "ops/governance/zen_audit.sh"
  legacy_withdraw:
    id: "action.legacy.withdraw"
    pre_gates: ["gate.net.port", "gate.proc.purity"]
    post_gates: ["gate.proc.purity", "gate.net.port"]
    handler: "ops/governance/handlers/legacy_withdraw.zsh"
```

## 9) Git Status (if repo)
```text
 M .0luka/scripts/promote_artifact.zsh
 D agents.md
 D architecture.md
 D catalog/README.md
 D index/README.md
 D prps/boq/boq_standard.md
 D prps/core_architecture.md
 D skills/index.md
 D telemetry/schema.md
?? .0luka/.DS_Store
?? .0luka/scripts/atg_multi_snap.zsh
?? .opencode/
?? .openwork/
?? core/architecture.md
?? core/governance/
?? observability/
?? ops/
?? runtime/

e586bf1 fix(core): Correct policy naming with yymmdd_ prefix
```

## 10) Process/Port Cross-check (optional)
```text
COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
rapportd   1029 icmini   13u  IPv4 0x61472fb526252ef7      0t0  TCP *:49162 (LISTEN)
rapportd   1029 icmini   14u  IPv6 0x3845c7c6b452546b      0t0  TCP *:49162 (LISTEN)
LINE       1097 icmini   46u  IPv4 0xa31404bcab9c48ef      0t0  TCP 127.0.0.1:50374 (LISTEN)
Anytype    1133 icmini   65u  IPv4   0xa525e3a6e7a5c8      0t0  TCP 127.0.0.1:51761 (LISTEN)
ControlCe  1146 icmini    8u  IPv4 0x6754c3ecf4b21c31      0t0  TCP *:7000 (LISTEN)
ControlCe  1146 icmini    9u  IPv6 0x27bbe73c03e5962a      0t0  TCP *:7000 (LISTEN)
ControlCe  1146 icmini   10u  IPv4 0x322ca4ad755bf2e2      0t0  TCP *:5000 (LISTEN)
ControlCe  1146 icmini   11u  IPv6 0x4b4c8e52a0d68e6d      0t0  TCP *:5000 (LISTEN)
anytypeHe  1578 icmini    7u  IPv4  0xcc14ae6dc36c9e9      0t0  TCP 127.0.0.1:49392 (LISTEN)
anytypeHe  1578 icmini    8u  IPv4 0x3342a29ff90f2caa      0t0  TCP 127.0.0.1:49393 (LISTEN)
anytypeHe  1578 icmini   67u  IPv4 0x6609d37b306fa383      0t0  TCP 127.0.0.1:47800 (LISTEN)
anytypeHe  1578 icmini   76u  IPv4  0x1111a338bc39791      0t0  TCP 127.0.0.1:31009 (LISTEN)
redis-ser  2778 icmini    6u  IPv4 0x4e16e2497dbb89be      0t0  TCP 127.0.0.1:6379 (LISTEN)
logioptio  2818 icmini   45u  IPv4 0xd3720e3b76d1c7cf      0t0  TCP *:59869 (LISTEN)
Google     8742 icmini   44u  IPv6 0x862bbdd71a94d8bc      0t0  TCP [::1]:7679 (LISTEN)
Cursor    21191 icmini   20u  IPv6 0x6943f2fd899f6af1      0t0  TCP *:57705 (LISTEN)
Cursor    22370 icmini   65u  IPv4 0x8dbad55cd9a7c183      0t0  TCP 127.0.0.1:57961 (LISTEN)
Cursor    22633 icmini   20u  IPv6 0xf96216a088210386      0t0  TCP *:58004 (LISTEN)
Python    25457 icmini    6u  IPv4 0xa5569a7499b54bd5      0t0  TCP *:7001 (LISTEN)
Autodesk  37217 icmini   17u  IPv4 0x64455e1eb410e98d      0t0  TCP 127.0.0.1:62477 (LISTEN)
Autodesk  37217 icmini   20u  IPv4 0x329c1fefcfaa2197      0t0  TCP 127.0.0.1:62478 (LISTEN)
Google    47735 icmini   54u  IPv4  0x1be1381b3883902      0t0  TCP 127.0.0.1:9222 (LISTEN)
Raycast   51322 icmini   41u  IPv4 0xb4ab8a078eba06df      0t0  TCP 127.0.0.1:7265 (LISTEN)
Python    54215 icmini    3u  IPv4 0xc49dbfdc0a01f92d      0t0  TCP 127.0.0.1:1559 (LISTEN)
node      54456 icmini   12u  IPv6  0xf2e9b08b54ecdf5      0t0  TCP *:8080 (LISTEN)
Electron  61295 icmini   50u  IPv6 0x68b19b254748e303      0t0  TCP *:59260 (LISTEN)
Antigravi 61585 icmini   33u  IPv4 0x33b7c0c62c6d0c99      0t0  TCP 127.0.0.1:59288 (LISTEN)
Antigravi 61585 icmini   47u  IPv4 0x77d577d2e8aeec39      0t0  TCP 127.0.0.1:59331 (LISTEN)
Antigravi 61585 icmini  105u  IPv4 0xfcc269d7b9cc61ef      0t0  TCP 127.0.0.1:59434 (LISTEN)
Antigravi 61586 icmini   29u  IPv4 0x516ccc3089c6f6bf      0t0  TCP 127.0.0.1:59287 (LISTEN)
Antigravi 61586 icmini   42u  IPv4 0x70ca77c5654ca83c      0t0  TCP 127.0.0.1:59330 (LISTEN)
Antigravi 61586 icmini   79u  IPv4 0x725534661e2bccc3      0t0  TCP 127.0.0.1:59464 (LISTEN)
language_ 61659 icmini   21u  IPv4 0x9a5de9cf56dea871      0t0  TCP 127.0.0.1:59314 (LISTEN)
language_ 61659 icmini   22u  IPv4 0xc36ae34cb3e7942d      0t0  TCP 127.0.0.1:59315 (LISTEN)
language_ 61659 icmini   40u  IPv4 0x7a1e7e44eca0812c      0t0  TCP 127.0.0.1:59355 (LISTEN)
language_ 61664 icmini   21u  IPv4 0x112f5bead409889e      0t0  TCP 127.0.0.1:59312 (LISTEN)
language_ 61664 icmini   22u  IPv4  0xedec2269bdeb002      0t0  TCP 127.0.0.1:59313 (LISTEN)
language_ 61664 icmini   43u  IPv4 0x17f82f41dc16eeae      0t0  TCP 127.0.0.1:59345 (LISTEN)
Antigravi 62714 icmini   20u  IPv6 0x1d7db65bf606a2c3      0t0  TCP *:59513 (LISTEN)
Antigravi 62749 icmini   20u  IPv6 0xb3d4de43ba8618ce      0t0  TCP *:59510 (LISTEN)
opencode  65524 icmini   15u  IPv4 0xeb75de0e704a6645      0t0  TCP 127.0.0.1:62314 (LISTEN)
Cursor    67341 icmini   20u  IPv6 0x8e12605825c07e8f      0t0  TCP *:63101 (LISTEN)
ollama    68850 icmini    3u  IPv4 0x800c896c75f6c5be      0t0  TCP 127.0.0.1:11434 (LISTEN)
Antigravi 98806 icmini   20u  IPv6 0x51921924baf341dd      0t0  TCP *:51810 (LISTEN)
```

## 11) Candidate Files (Top suspects)
```text
/Users/icmini/0luka/core/governance/ontology.yaml
/Users/icmini/0luka/observability/audit/260125_030457_judicial_reality_audit.md
/Users/icmini/0luka/observability/audit/260125_030504_judicial_reality_audit.md
/Users/icmini/0luka/observability/audit/260125_030527_judicial_reality_audit.md
/Users/icmini/0luka/observability/audit/260125_030558_judicial_reality_audit.md
/Users/icmini/0luka/ops/tools/tools/zen_claim_gate.py
/Users/icmini/0luka/ops/tools/wo_audit_root_regen_v1.zsh
/Users/icmini/0luka/ops/governance/gate_runnerd.py
/Users/icmini/0luka/ops/governance/id_counter.py
/Users/icmini/0luka/ops/governance/gate_runner.py
/Users/icmini/0luka/ops/governance/seal_stl.zsh
/Users/icmini/0luka/ops/governance/zen_audit.sh
/Users/icmini/0luka/ops/governance/judicial_reality_audit.zsh
/Users/icmini/0luka/ops/governance/verify_chain.py
```
