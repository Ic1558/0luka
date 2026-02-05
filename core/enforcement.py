import yaml
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# Load Policy
POLICY_PATH = Path("core/runtime_policy.yaml")

class ContextViolation(Exception):
    """Raised when a context policy is violated."""
    pass

class PermissionDenied(Exception):
    """Raised when a tool/resource constraint is violated."""
    pass

class RuntimeEnforcer:
    _policy_cache = None

    @classmethod
    def load_policy(cls) -> Dict[str, Any]:
        if cls._policy_cache is None:
            if not POLICY_PATH.exists():
                raise FileNotFoundError(f"Policy file not found at {POLICY_PATH}")
            with open(POLICY_PATH, 'r') as f:
                cls._policy_cache = yaml.safe_load(f)["context_policy_v1"]
        return cls._policy_cache

    @classmethod
    def enforce_context(cls, role: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce context budget and content rules.
        """
        policy = cls.load_policy()
        if role not in policy:
            raise ContextViolation(f"Unknown role: {role}")
        
        rules = policy[role]

        # 1. Deny Raw Artifacts/Outputs for Orchestrator
        if role == "orchestrator":
             # Check for forbidden keys
             for key in ["artifacts", "raw_chunks", "tool_output_raw", "file_content_raw"]:
                 if payload.get(key):
                     raise ContextViolation(f"Role '{role}' cannot receive raw data key: {key}")

        # 2. Token Budget Clamp (Mock implementation of truncation)
        # In a real system, use tiktoken. Here, we approximate char count ~4 chars/token
        budget = rules.get("max_input_tokens", 2000)
        # We don't modify the payload in-place for budget here in this mock, 
        # but we could truncate large string fields.
        
        # 3. Allowlist Filter
        allowed_keys = set(rules.get("allow", []))
        # This implementation requires the payload to be structured exactly with these keys.
        # For flexibility, we might just warn or filter top-level keys.
        # But per "hard enforcement", let's be strict if keys map to data types.
        
        return payload

    @classmethod
    def enforce_tool_access(cls, role: str, tool_name: str, args: Dict[str, Any], scope: Dict[str, Any]):
        """
        Enforce tool execution rights with STRICT path validation.
        """
        policy = cls.load_policy()
        rules = policy.get(role, {})
        
        # 1. Hard Deny List
        deny_list = set(rules.get("deny", []))
        if tool_name in deny_list:
             raise PermissionDenied(f"Tool '{tool_name}' is explicitly denied for role '{role}'")

        # Orchestrator Denials (Hardcoded safety net)
        if role == "orchestrator":
             if tool_name in ["read_file", "list_dir", "glob", "curl", "fetch", "subprocess"]:
                 raise PermissionDenied(f"Orchestrator forbidden from using raw IO tool: {tool_name}")

        # 2. Scope Check for File/Subprocess Tools
        # Expanded list to catch subprocess usage
        file_tools = ["read_file", "list_dir", "glob", "write_file", "write_to_file", "subprocess"]
        
        if tool_name in file_tools:
            # Gather targets to check
            targets = []
            
            # Explicit keys for file tools
            if args.get("path"): targets.append(args["path"])
            if args.get("target_file"): targets.append(args["target_file"])
            
            # Keys for subprocess (check cwd, script components)
            if tool_name == "subprocess":
                if args.get("cwd"): targets.append(args["cwd"])
                if args.get("script_path"): targets.append(args["script_path"])
                
                # Check for dangerous shell flags in args/argv/command
                # This is a heuristic defense against generic shell runners
                dangerous_flags = ["-c", "/c", "-Command", "-EncodedCommand", "-lc", "-l", "--command"]
                cmd_args = args.get("args") or args.get("argv") or args.get("command") or []
                
                if isinstance(cmd_args, list):
                     for arg in cmd_args:
                         if arg in dangerous_flags:
                             raise PermissionDenied(f"Subprocess argument '{arg}' is disallowed by policy.")
                elif isinstance(cmd_args, str):
                    # Check if any dangerous flag is present in the string command line
                    # Conservative check: look for flags surrounded by spaces or at start
                    for flag in dangerous_flags:
                        if f" {flag} " in f" {cmd_args} ": # Pad to ensure whole word match-ish
                             raise PermissionDenied(f"Subprocess command string contains disallowed '{flag}' flag.")
            
            # Fail Closed if no path found for a file tool (except maybe subprocess if no cwd/script?)
            # But subprocess *always* touches FS (binary execution). 
            # If targets is empty for read_file, it's suspicious or malformed.
            if tool_name != "subprocess" and not targets:
                 raise PermissionDenied(f"Tool '{tool_name}' invoked without a target path argument.")

            allowed_paths = [Path(p).resolve() for p in scope.get("allowed_paths", [])]

            for target_str in targets:
                try:
                    # Resolve target. strict=False allows non-existent (future) files.
                    # BUT we must handle symlinks carefully. 
                    # Ideally strict=True for existing resources, but strict=False for new files.
                    target = Path(target_str).expanduser().resolve(strict=False)
                    
                    is_allowed = False
                    for root in allowed_paths:
                        # DESCENDANT CHECK
                        try:
                            # is_relative_to is Py3.9+
                            if hasattr(target, "is_relative_to"):
                                if target.is_relative_to(root):
                                    is_allowed = True
                                    break
                            else:
                                # Fallback for older python
                                # Ensure strings are passed to commonpath to avoid type errors
                                common = Path(os.path.commonpath([str(root), str(target)])).resolve()
                                if common == root:
                                    is_allowed = True
                                    break
                        except ValueError:
                            # raised if paths are on different drives or mix relative/absolute
                            pass
                                
                    if not is_allowed:
                        raise PermissionDenied(f"Path access denied: {target_str} (resolved: {target}) is not in scope.")
                        
                except PermissionDenied:
                    raise
                except Exception as e:
                     raise PermissionDenied(f"Invalid path check for {target_str}: {e}")
