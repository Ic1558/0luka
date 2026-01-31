#!/usr/bin/env python3
import json
import os
import time
import hashlib
from pathlib import Path
from typing import List

# Use environment variable for root or default to ~/0luka
ROOT = Path(os.environ.get("OLUKA_ROOT", Path.home() / "0luka")).resolve()
OLUKA_TELEMETRY_ROOT = ROOT / "observability" / "telemetry"
OLUKA_TELEMETRY_ROOT.mkdir(parents=True, exist_ok=True)

class PanicAbort(RuntimeError):
    pass

class BaseAgent:
    CALL_SIGN = "[BASE]"
    AGENT_NAME = "base"
    MODE = "readonly"  # readonly | planner | executor | sandbox
    ROOT = ROOT # Export for subclasses

    # ---- Permission Matrix ----
    ALLOW_WRITE_PATHS: List[Path] = []
    DENY_WRITE_PATHS: List[Path] = [
        ROOT / "core",
        ROOT / "runtime",
        ROOT / "governance",
        ROOT / "core_brain" / "governance",
    ]

    def __init__(self):
        self.start_ts = time.time()
        self.hostname = os.uname().nodename.lower()

    # ---------- Guards ----------
    def _panic(self, reason: str):
        self.log_json({
            "level": "PANIC",
            "agent": self.AGENT_NAME,
            "call_sign": self.CALL_SIGN,
            "reason": reason,
        })
        raise PanicAbort(f"[{self.CALL_SIGN}] FATAL: {reason}")

    def enforce_call_sign(self):
        if not self.CALL_SIGN.startswith("[") or not self.CALL_SIGN.endswith("]"):
            self._panic("Invalid call-sign format")
        print(f"{self.CALL_SIGN} Identity match verified.")

    def _is_path_allowed(self, path: Path) -> bool:
        path = path.resolve()
        # 1. Deny check (Blacklist)
        for deny in self.DENY_WRITE_PATHS:
            if path.is_relative_to(deny):
                return False
        # 2. Allow check (Whitelist)
        if self.ALLOW_WRITE_PATHS:
            return any(path.is_relative_to(p) for p in self.ALLOW_WRITE_PATHS)
        return False

    def write_file(self, path: Path, content: str):
        if self.MODE == "readonly":
            self._panic("Write attempted in READ-ONLY agent")

        path = path.resolve()
        if not self._is_path_allowed(path):
            self._panic(f"Write denied to path: {path}")

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)

    # ---------- Logging ----------
    def log_json(self, payload: dict):
        payload.update({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "agent": self.AGENT_NAME,
            "call_sign": self.CALL_SIGN,
            "host": self.hostname,
        })
        line = json.dumps(payload, ensure_ascii=False)
        print(line)
        # Always use the canonical root defined in the Base class
        target_log = OLUKA_TELEMETRY_ROOT / f"{self.AGENT_NAME}.jsonl"
        with open(target_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ---------- Utilities ----------
    @staticmethod
    def sha256_of(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
