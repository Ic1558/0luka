#!/usr/bin/env python3
"""
Phase 12: Mission Control Read-Only Server
Provides JSON access to observability artifacts.
"""
import http.server
import socketserver
import json
import os
from pathlib import Path
from annotation_handler import append_annotation

PORT = 8081
REPO_ROOT = Path(__file__).resolve().parents[3]

class MissionControlHandler(http.server.SimpleHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        # Strict Read-Only: Only specific observability paths allowed
        allowed_paths = [
            "/observability/activity/activity.jsonl",
            "/observability/audit/reasoning.jsonl",
            "/observability/artifacts/dispatcher_heartbeat.json",
            "/observability/artifacts/dispatch_latest.json",
            "/observability/artifacts/run_provenance.jsonl"
        ]
        
        if self.path == "/":
            self.path = "/tools/ops/mission_control/ui/index.html"
            return super().do_GET()
        
        if self.path.startswith("/api/"):
            resource = self.path.replace("/api/", "")
            full_path = REPO_ROOT / resource
            
            if resource in [p.lstrip("/") for p in allowed_paths] and full_path.exists():
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                
                if resource.endswith(".jsonl"):
                    # Return last 100 lines for efficiency
                    lines = full_path.read_text().splitlines()[-100:]
                    self.wfile.write(json.dumps([json.loads(l) for l in lines]).encode())
                else:
                    self.wfile.write(full_path.read_bytes())
                return
            
            self.send_error(403, "Access Denied / Not in Observability Layer")
            return

        # Serve static assets for the UI
        if self.path.startswith("/ui/"):
            self.path = f"/tools/ops/mission_control{self.path}"
            return super().do_GET()

        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/annotations":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
            row = append_annotation(payload)
            self._send_json(200, {"ok": True, "annotation": row})
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})

if __name__ == "__main__":
    os.chdir(REPO_ROOT)
    with socketserver.TCPServer(("", PORT), MissionControlHandler) as httpd:
        print(f"Mission Control (Read-Only) serving at port {PORT}")
        httpd.serve_forever()
