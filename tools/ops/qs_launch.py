#!/usr/bin/env python3
"""
QS Engine Launcher
Spins up the Universal QS Engine background server and opens the browser UI.
"""

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


def wait_for_server(url: str, timeout: int = 10) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    repo_root = Path(__file__).parent.parent.parent.absolute()
    engine_dir = repo_root / "repos" / "qs"
    
    if not engine_dir.exists():
        print(f"Error: Canonical QS module checkout not found at {engine_dir}")
        print("Clone or sync https://github.com/Ic1558/qs into repos/qs before launching.")
        sys.exit(1)

    # Launch the QS Engine service
    print("Starting Universal QS Engine from repos/qs...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(engine_dir / "src")
    cmd = [
        sys.executable, "-m", "universal_qs_engine.cli", "serve-health"
    ]
    
    # Run it as a detached process (or keep blocking until user exits)
    # Backgrounding:
    process = subprocess.Popen(
        cmd,
        cwd=str(engine_dir),
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    health_url = "http://127.0.0.1:7084/api/health"
    print(f"Waiting for {health_url} to come online...")
    
    if wait_for_server(health_url):
        ui_url = "http://127.0.0.1:7084/"
        print(f"Server is up! Opening {ui_url} in browser...")
        webbrowser.open(ui_url)
        
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\nShutting down Universal QS Engine...")
            process.terminate()
            process.wait()
    else:
        print("Error: Server failed to start or did not pass health check.")
        process.terminate()
        sys.exit(1)


if __name__ == "__main__":
    main()
