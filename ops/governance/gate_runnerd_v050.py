import os
import socket
import json
import yaml
import hashlib
import struct
import time
from pathlib import Path
from id_counter import IDCounter

class GateRunnerDaemon:
    ROOT = Path("/Users/icmini/0luka")
    EVID_BASE = ROOT / "observability/stl/evidence"
    BEACON_PATH = ROOT / "observability/stl/ledger/global_beacon.jsonl"
    SOCK_PATH = ROOT / "runtime/sock/gate_runner.sock"
    ONTOLOGY_PATH = ROOT / "core/governance/ontology.yaml"
    MAX_FRAME_BYTES = 1024 * 1024
    LOG_THROTTLE_SEC = 30
    JSON_ERROR_BACKOFF_SEC = 0.2
    MUTATION_CMDS = {"run_task", "execute_action", "set_alarm"}
    CLIENT_ID = "rpc_client"

    ACTION_TABLE = {
        "action.service.restart": "ops/governance/handlers/service_restart.zsh",
        "action.system.audit": "ops/governance/zen_audit.sh",
        "action.legacy.withdraw": "ops/governance/handlers/legacy_withdraw.zsh",
        # v0.5.0 MCP Hand Actions
        "action.followup.generate": "tools/claude_tools/generate_followup_data.zsh",
        "action.ram.snapshot": "tools/ram_monitor.zsh",
        "action.mls.watch": "tools/mls_file_watcher.zsh"
    }

    def __init__(self):
        self.counter = IDCounter()
        self.ALARM_ACTIVE = False
        self._owner_uid = os.geteuid()
        self._log_last = {}
        self._rpc_client_path = str(self.ROOT / "ops/governance/rpc_client.py")
        
        # v0.4.1 Startup Seals (The Golden State)
        self.startup_ontology_hash = self._compute_file_hash(self.ONTOLOGY_PATH)
        self.handler_seals = self._seal_handlers()
        
        # Load initial ontology state (trusted because of seal)
        self.ontology = self.load_ontology()

    def _compute_file_hash(self, path):
        """Helper to compute deterministic SHA256 of a file."""
        if not path.exists(): return None
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _seal_handlers(self):
        """Seal all allowed action handlers at startup."""
        seals = {}
        for action_id, rel_path in self.ACTION_TABLE.items():
            path = (self.ROOT / rel_path).resolve() # Resolve symlinks
            if path.exists():
                seals[action_id] = self._compute_file_hash(path)
        return seals

    def verify_ontology_integrity(self):
        """Cross-check on-disk ontology against startup seal."""
        current_hash = self._compute_file_hash(self.ONTOLOGY_PATH)
        if current_hash != self.startup_ontology_hash:
            raise RuntimeError(f"CRITICAL: Ontology Tampered! {current_hash} != {self.startup_ontology_hash}")
        return current_hash

    def load_ontology(self):
        with open(self.ONTOLOGY_PATH, 'r') as f:
            return yaml.safe_load(f)

    def get_last_beacon_hash(self):
        """Retrieve the hash of the last beacon entry for chaining."""
        if not self.BEACON_PATH.exists(): return None
        try:
            # Efficiently read last line using seek
            with open(self.BEACON_PATH, 'rb') as f:
                try:
                    f.seek(-2, os.SEEK_END)
                    while f.read(1) != b'\n':
                        f.seek(-2, os.SEEK_CUR)
                except OSError:
                    f.seek(0)
                last_line = f.readline().decode()
                if not last_line: return None
                return json.loads(last_line).get("this_beacon_hash")
        except: return None

    def log_beacon(self, tk_key, task_id, action, result_hash):
        """Append to Global Chain Beacon with Forensic Chaining."""
        prev_hash = self.get_last_beacon_hash()
        
        entry = {
            "tk_key": tk_key,
            "task_id": task_id,
            "action": action,
            "result_hash": result_hash,
            "ontology_hash": self.startup_ontology_hash,
            "prev_beacon_hash": prev_hash
        }
        
        # Calculate this_beacon_hash
        json_str = json.dumps(entry, sort_keys=True)
        this_hash = hashlib.sha256(json_str.encode()).hexdigest()
        entry["this_beacon_hash"] = this_hash
        
        self.BEACON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.BEACON_PATH, 'a') as f:
            f.write(json.dumps(entry) + "\n")

    def get_prev_attn_hash(self, task_id):
        task_evid_dir = self.EVID_BASE / task_id
        if not task_evid_dir.exists(): return None
        attestations = sorted([f for f in task_evid_dir.glob("*.json")])
        if not attestations: return None
        with open(attestations[-1], 'r') as f:
            data = json.load(f)
            return data.get("this_attn_hash")

    def verify_gate(self, gate_id):
        # Integrity Check before any gate logic
        self.verify_ontology_integrity()
        
        if gate_id == "gate.fs.root":
            allowed = set(self.ontology['invariants']['strict_root']['allow'])
            current = set([f.name for f in self.ROOT.iterdir() if not f.name.startswith('.')])
            violations = current - allowed
            return (not violations, {"violations": list(violations)})
        if gate_id == "gate.net.port":
            try:
                import socket as py_socket
                with py_socket.socket(py_socket.AF_INET, py_socket.SOCK_STREAM) as s:
                    ok = s.connect_ex(('localhost', 7001)) == 0
                return (ok, {"port": 7001})
            except: return (False, {"port": 7001, "error": "socket check fail"})
        if gate_id == "gate.proc.purity":
            import subprocess
            res = subprocess.check_output("ps aux | grep -Ei 'mary_dispatcher|clc_bridge|shell_watcher' | grep -v grep | wc -l", shell=True).decode()
            count = int(res.strip())
            return (count == 0, {"legacy_proc_count": count})
        return (False, {"error": f"Unknown Gate: {gate_id}"})

    def run_task(self, task_id):
        # Integrity Check
        self.verify_ontology_integrity()

        task_path = self.ROOT / "observability/stl/tasks/open" / task_id
        if not task_path.exists():
            return {"error": "Task file not found"}
        
        with open(task_path, 'r') as f:
            task = yaml.safe_load(f)

        prev_hash = self.get_prev_attn_hash(task_id)
        results = {g: self.verify_gate(g) for g in task.get('verification', {}).get('gates', [])}
        
        tk_key = self.counter.get_next_tk()
        slug = task_id.split('_')[2] if '_' in task_id else "task"
        
        content = {
            "attestation_version": "0.4.1",
            "task_id": task_id,
            "tk_key": tk_key,
            "prev_attn_hash": prev_hash,
            "results": results,
            "zen": all(res[0] for res in results.values()),
            "meta": {"wall_time_ref": "host_lock"},
            "ontology_seal": self.startup_ontology_hash
        }
        
        json_str = json.dumps(content, sort_keys=True)
        h8 = hashlib.sha256(json_str.encode()).hexdigest()[:8]
        this_hash = hashlib.sha256(json_str.encode()).hexdigest()
        content["this_attn_hash"] = this_hash
        
        evid_dir = self.EVID_BASE / task_id
        evid_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{tk_key}_attn_{slug}_{h8}.json"
        
        with open(evid_dir / filename, 'w') as f:
            json.dump(content, f, indent=2, sort_keys=True)
        
        self.log_beacon(tk_key, task_id, "run_gates", this_hash)
            
        return {"status": "ok", "attestation_id": filename, "zen": content["zen"]}

    def execute_action(self, task_id, action_id):
        if self.ALARM_ACTIVE:
            return {"error": "ALARM ACTIVE: System Frozen"}
            
        # Integrity Check
        self.verify_ontology_integrity()

        import subprocess
        handler_rel_path = self.ACTION_TABLE.get(action_id)
        if not handler_rel_path:
            return {"error": f"Action {action_id} not in JUDICIAL allowlist"}
        
        handler_path = (self.ROOT / handler_rel_path).resolve()
        
        # Action Purity (Anti-Tamper)
        current_hash = self._compute_file_hash(handler_path)
        expected_hash = self.handler_seals.get(action_id)
        
        if current_hash != expected_hash:
             return {"error": f"CRITICAL: Handler Tampered! {action_id} hash mismatch."}

        try:
            output = subprocess.check_output([str(handler_path)], stderr=subprocess.STDOUT).decode()
            tk_key = self.counter.get_next_tk()
            result_hash = hashlib.sha256(output.encode()).hexdigest()[:8]
            self.log_beacon(tk_key, task_id, f"action:{action_id}", result_hash)
            return {"status": "executed", "output": output}
        except subprocess.CalledProcessError as e:
            return {"error": "Handler failed", "output": e.output.decode()}
        except Exception as e:
            return {"error": f"Execution error: {str(e)}"}

    def set_alarm(self, status: bool):
        self.ALARM_ACTIVE = status
        return {"status": "alarm_set", "active": self.ALARM_ACTIVE}

    def authorize(self, action_id, args=None, task_id=None):
        """
        v0.5.0: Pre-execution Authorization (Read-Only).
        Checks:
        1. Alarm Freeze (blocks everything)
        2. Ontology Integrity
        3. Action Allowlist (ACTION_TABLE)
        4. Handler Seal Integrity
        Returns: {"allowed": bool, "reason": str, ...}
        """
        # 1. Alarm Check
        if self.ALARM_ACTIVE:
            return {"ok": True, "allowed": False, "reason": "ALARM ACTIVE: System Frozen"}

        # 2. Integrity Check
        try:
            self.verify_ontology_integrity()
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}

        # 3. Allowlist Check
        handler_rel_path = self.ACTION_TABLE.get(action_id)
        if not handler_rel_path:
            return {"ok": True, "allowed": False, "reason": f"Action {action_id} not in allowlist"}

        # 4. Seal Check
        handler_path = (self.ROOT / handler_rel_path).resolve()
        current_hash = self._compute_file_hash(handler_path)
        expected_hash = self.handler_seals.get(action_id)

        if current_hash != expected_hash:
             return {"ok": True, "allowed": False, "reason": f"CRITICAL: Handler Tampered! {action_id} hash mismatch."}

        # 5. Beacon Log (Audit)
        tk_key = self.counter.get_next_tk()
        
        # Deterministic result hash for the authorization decision
        decision_data = {
            "allowed": True, 
            "action_id": action_id, 
            "handler_hash": current_hash,
            "args_hash": hashlib.sha256(json.dumps(args or {}, sort_keys=True).encode()).hexdigest()
        }
        result_hash = hashlib.sha256(json.dumps(decision_data, sort_keys=True).encode()).hexdigest()[:8]
        
        self.log_beacon(tk_key, task_id or "-", f"authorize:{action_id}", result_hash)

        return {
            "ok": True, 
            "allowed": True, 
            "reason": "Policy Check Passed", 
            "ontology_hash": self.startup_ontology_hash,
            "handler_hash": current_hash
        }


    def get_peer_uid(self, conn):
        """Robustly get peer UID (supports standard and ctypes fallback)."""
        # Method 1: Standard Python (if available)
        if hasattr(conn, 'getpeereid'):
            return conn.getpeereid()[0]
            
        # Method 2: ctypes call to getpeereid (macOS/BSD)
        try:
            import ctypes
            import ctypes.util
            libc = ctypes.CDLL(ctypes.util.find_library('c'))
            uid = ctypes.c_uint32()
            gid = ctypes.c_uint32()
            # int getpeereid(int fildes, uid_t *uid, gid_t *gid);
            ret = libc.getpeereid(conn.fileno(), ctypes.byref(uid), ctypes.byref(gid))
            if ret == 0:
                return uid.value
            else:
                print(f"DEBUG: ctypes getpeereid returned {ret}")
        except Exception as e:
            print(f"DEBUG: ctypes fallback failed: {e}")
            
        return None

    def verify_identity(self, conn):
        try:
            peer_uid = self.get_peer_uid(conn)
            if peer_uid is None:
                print("SECURITY: Could not determine peer identity (Platform issue?)")
                return False
                
            if peer_uid != self._owner_uid:
                print(f"SECURITY: Blocked connection from UID {peer_uid} (Expected {self._owner_uid})")
                return False
            return True
        except Exception as e:
            print(f"SECURITY: Failed to get peer identity: {e}")
            return False

    def _log_throttled(self, key, message):
        now = time.time()
        last = self._log_last.get(key, 0)
        if now - last >= self.LOG_THROTTLE_SEC:
            self._log_last[key] = now
            print(message)

    def _authorized_mutation(self, req):
        client_id = req.get("client_id")
        client_path = req.get("client_path")
        if client_id != self.CLIENT_ID or client_path != self._rpc_client_path:
            self._log_throttled(
                "unauthorized_mutation",
                f"SECURITY: Unauthorized mutation path client_id={client_id} client_path={client_path}"
            )
            return False
        return True

    def handle_client(self, conn):
        try:
            if not self.verify_identity(conn): return
            
            # Read 4-byte length
            len_bytes = b''
            while len(len_bytes) < 4:
                chunk = conn.recv(4 - len(len_bytes))
                if not chunk: return # Clean disconnect
                len_bytes += chunk
                
            msg_len = struct.unpack('>I', len_bytes)[0]
            
            # v0.4.1 Frame Cap
            if msg_len == 0:
                self._log_throttled("empty_frame", "SECURITY: Empty frame length (0). Dropping.")
                return
            if msg_len > self.MAX_FRAME_BYTES:
                self._log_throttled("oversize_frame", f"SECURITY: Message too large ({msg_len} bytes). Dropping.")
                return

            data = b''
            while len(data) < msg_len:
                chunk = conn.recv(min(4096, msg_len - len(data)))
                if not chunk:
                    self._log_throttled("incomplete_body", "ERROR: Incomplete message body")
                    return
                data += chunk
                
            try:
                text = data.decode()
            except UnicodeDecodeError:
                self._log_throttled("invalid_utf8", "SECURITY: Invalid UTF-8 payload. Dropping.")
                return
            if not text.strip():
                self._log_throttled("empty_payload", "SECURITY: Empty payload. Dropping.")
                return
            try:
                req = json.loads(text)
            except json.JSONDecodeError:
                self._log_throttled("invalid_json", "SECURITY: Invalid JSON payload. Dropping.")
                time.sleep(self.JSON_ERROR_BACKOFF_SEC)
                return
            if not isinstance(req, dict):
                self._log_throttled("invalid_payload_type", "SECURITY: Non-object JSON payload. Dropping.")
                return
            cmd = req.get("cmd")
            
            resp = {"error": "Unknown command"}
            try:
                if cmd in self.MUTATION_CMDS and not self._authorized_mutation(req):
                    resp = {"error": "Unauthorized mutation path"}
                elif cmd == "run_task":
                    resp = self.run_task(req["task_id"])
                elif cmd == "execute_action":
                    resp = self.execute_action(req["task_id"], req["action_id"])
                elif cmd == "verify_gate":
                    resp = self.verify_gate(req["gate_id"])
                elif cmd == "set_alarm":
                    resp = self.set_alarm(req["active"])
                elif cmd == "authorize":
                    # Support 'action' or 'action_id' for compatibility
                    a_id = req.get("action") or req.get("action_id")
                    resp = self.authorize(a_id, req.get("args"), req.get("task_id"))
            except RuntimeError as e: # Catch Integrity Failures
                 resp = {"error": str(e)}

            payload = json.dumps(resp).encode()
            try:
                conn.sendall(struct.pack('>I', len(payload)) + payload)
            except BrokenPipeError:
                pass # Client disconnected
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            try:
                err_payload = json.dumps({"error": str(e)}).encode()
                conn.sendall(struct.pack('>I', len(err_payload)) + err_payload)
            except: pass
        finally: conn.close()

    def run(self):
        if self.SOCK_PATH.exists(): self.SOCK_PATH.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.SOCK_PATH))
        server.listen(5)
        os.chmod(self.SOCK_PATH, 0o660)
        print(f"Judicial Daemon v0.4.1 listening on {self.SOCK_PATH}...")
        
        while True:
            try:
                conn, _ = server.accept()
                self.handle_client(conn)
            except Exception as e:
                print(f"CRITICAL SERVER ERROR: {e}")

if __name__ == "__main__":
    daemon = GateRunnerDaemon()
    daemon.run()
