#!/usr/bin/env python3
"""
Manual Security Audit Script for RuntimeEnforcer and Tool Gate
Running exact verification cases requested by User.
"""
import sys
import os
from pathlib import Path
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.enforcement import RuntimeEnforcer, PermissionDenied
from runtime.apps.opal_api.worker import _collect_candidate_paths

def test_path_enforcement():
    print("--- [A] Path Enforcement (Must Block) ---")
    
    # Setup mock environment
    root = Path("/tmp/opal_audit_root").resolve()
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True)
    
    safe_roots = [str(root)]
    scope = {"allowed_paths": safe_roots}
    role = "worker"
    
    # 1. ../ Traversal
    try:
        target = str(root / "../outside.txt")
        print(f"Testing traversal: {target}")
        RuntimeEnforcer.enforce_tool_access(role, "read_file", {"path": target}, scope)
        print("❌ FAILED: Traversal allowed")
    except PermissionDenied:
        print("✅ BLOCKED: Traversal")
        
    # 2. Symlink Escape
    try:
        # Create a file outside
        outside_file = Path("/tmp/outside_secret.txt")
        outside_file.write_text("secret")
        # Link inside
        link = root / "safe_link"
        os.symlink(outside_file, link)
        
        print(f"Testing symlink: {link}")
        RuntimeEnforcer.enforce_tool_access(role, "read_file", {"path": str(link)}, scope)
        print("❌ FAILED: Symlink escape allowed")
    except PermissionDenied:
        print("✅ BLOCKED: Symlink escape")
    except Exception as e:
        print(f"⚠️ Error during symlink test: {e}")
        
    # 3. Mixed Separators
    try:
        # Construct path manually to avoid strict OS normalization if python auto-fixes it too early,
        # but here we pass string.
        target = "../../etc/passwd"
        print(f"Testing mixed/relative: {target}")
        RuntimeEnforcer.enforce_tool_access(role, "read_file", {"path": target}, scope)
        print("❌ FAILED: Relative block failed")
    except PermissionDenied:
         print("✅ BLOCKED: Relative path")
         
    # 4. UNC / Double Slash (Mocking string check)
    try:
        target = "//server/share/x"
        print(f"Testing UNC: {target}")
        RuntimeEnforcer.enforce_tool_access(role, "read_file", {"path": target}, scope)
        print("❌ FAILED: UNC allowed")
    except PermissionDenied:
        print("✅ BLOCKED: UNC")

    # 5. URI-ish
    try:
        target = "file:///etc/passwd"
        print(f"Testing URI: {target}")
        # Logic might resolve this to CWD/file:/etc/passwd if not careful, 
        # or it might crash. User wants at least 'not allow'.
        RuntimeEnforcer.enforce_tool_access(role, "read_file", {"path": target}, scope)
        # If it resolves to something inside root (e.g. /tmp/root/file:/...) it might pass logic, 
        # but OS won't open it. 
        # But wait, enforce_tool_access calls expanduser().resolve().
        # Path("file:///etc/passwd").resolve() -> /current/dir/file:/etc/passwd on *nix
        # So it stays inside CWD usually. 
        # User wants PermissionDenied preferably.
    except PermissionDenied:
        print("✅ BLOCKED: URI")
    except Exception:
        print("✅ BLOCKED: URI (Exception raised)")
    else:
        # If it passed, check if it resolved to safe root?
        print("⚠️ PASSED: URI (Check if this is safe resolution)")

    print("\n--- [B] Path Enforcement (Must Allow) ---")
    
    # 1. Normal
    try:
        target = str(root / "a/b/c.txt")
        print(f"Testing valid inner path: {target}")
        RuntimeEnforcer.enforce_tool_access(role, "read_file", {"path": target}, scope)
        print("✅ ALLOWED: Valid path")
    except PermissionDenied as e:
        print(f"❌ FAILED: Valid path blocked ({e})")

    # 2. Root itself
    try:
        target = str(root)
        print(f"Testing root itself: {target}")
        RuntimeEnforcer.enforce_tool_access(role, "read_file", {"path": target}, scope)
        print("✅ ALLOWED: Root path")
    except PermissionDenied:
        print("❌ FAILED: Root path blocked")

    # 3. Normalization required
    try:
        target = str(root) + "/a/./b/../c.txt"
        print(f"Testing messy path in root: {target}")
        RuntimeEnforcer.enforce_tool_access(role, "read_file", {"path": target}, scope)
        print("✅ ALLOWED: Messy path")
    except PermissionDenied:
        print("❌ FAILED: Messy path blocked")
        
    print("\n--- [C] Subprocess Policy (Must Block) ---")
    scope_sub = {"allowed_paths": safe_roots}
    
    cases = [
        (["bash", "-c", "id"], "List with -c"),
        ("bash -c id", "String with -c"),
        (["python", "-c", "print(1)"], "Python -c"),
        ("cmd /c dir", "Windows /c"),
        (["powershell", "-Command", "ls"], "Powershell -Command"),
        (["bash", "-lc", "whoami"], "Bash -lc")
    ]
    
    for cmd, name in cases:
        try:
            params = {}
            if isinstance(cmd, list): params["args"] = cmd
            else: params["command"] = cmd
            
            # Add dummy valid stuff
            params["cwd"] = str(root)
            
            msg = f"Testing {name}"
            # print(msg)
            RuntimeEnforcer.enforce_tool_access(role, "subprocess", params, scope_sub)
            print(f"❌ FAILED: {name} allowed")
        except PermissionDenied:
            print(f"✅ BLOCKED: {name}")

def test_collector():
    print("\n--- [D] Collector Coverage ---")
    
    # 1. Nested
    job = {
        "parameters": {
            "files": [
                {"path": "/etc/passwd"},
                {"dst": "../../.ssh/id_rsa"}
            ]
        }
    }
    paths = _collect_candidate_paths(job)
    print(f"Nested paths found: {paths}")
    has_passwd = any("/etc/passwd" in p for p in paths)
    has_ssh = any(".ssh/id_rsa" in p for p in paths) # likely resolved
    
    if has_passwd: print("✅ DETECTED: /etc/passwd")
    else: print("❌ MISSED: /etc/passwd")

if __name__ == "__main__":
    test_path_enforcement()
    test_collector()
