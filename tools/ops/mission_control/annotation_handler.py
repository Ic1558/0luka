#!/usr/bin/env python3
"""Phase 13 annotation sink (append-only, no execution authority)."""
from __future__ import annotations

import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

ALLOWED_ACTIONS = {"acknowledge", "disagree", "classify", "note"}
FORBIDDEN_COMMAND_PATTERNS = [
    re.compile(r"(;|&&|\|\||\$\(|`)", re.IGNORECASE),
    re.compile(r"\b(rm\s+-rf|sudo\s+|dispatch|core/dispatch|interface/inbox)\b", re.IGNORECASE),
]
TOKEN_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b(api[_-]?key|token|password|secret)\b", re.IGNORECASE),
]


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _repo_root() -> Path:
    raw = os.environ.get("ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve(strict=False)
    return Path(__file__).resolve().parents[3]


def _annotation_path() -> Path:
    return _repo_root() / "observability" / "annotations" / "annotations.jsonl"


def ensure_storage() -> Path:
    path = _annotation_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_text(text: str) -> str:
    out = str(text)
    out = re.sub(r"/Users/[A-Za-z0-9._-]+", "PATH_REDACTED", out)
    for pat in TOKEN_PATTERNS:
        out = pat.sub("TOKEN_REDACTED", out)
    return out.strip()


def _contains_forbidden_command(text: str) -> bool:
    return any(p.search(text) for p in FORBIDDEN_COMMAND_PATTERNS)


def validate_annotation(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("annotation_invalid_payload")

    event_id = str(payload.get("event_id") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    comment = str(payload.get("comment") or "").strip()
    author = str(payload.get("author") or "human").strip()
    ts = str(payload.get("ts") or _utc_now()).strip()

    if not event_id:
        raise ValueError("annotation_missing_event_id")
    if action not in ALLOWED_ACTIONS:
        raise ValueError("annotation_invalid_action")
    if not author:
        raise ValueError("annotation_missing_author")

    combined = f"{comment} {event_id} {author}"
    if _contains_forbidden_command(combined):
        raise ValueError("annotation_command_like_rejected")

    return {
        "schema_version": "annotation.v1",
        "ts": ts,
        "event_id": _sanitize_text(event_id),
        "action": action,
        "comment": _sanitize_text(comment),
        "author": _sanitize_text(author),
    }


def append_annotation(payload: Dict[str, Any]) -> Dict[str, Any]:
    row = validate_annotation(payload)
    path = ensure_storage()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


class AnnotationHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, body: Dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/annotations":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            row = append_annotation(payload)
            self._send_json(200, {"ok": True, "annotation": row})
        except Exception as exc:  # fail-closed
            self._send_json(400, {"ok": False, "error": str(exc)})


def run_server(host: str = "127.0.0.1", port: int = 8091) -> None:
    ensure_storage()
    server = HTTPServer((host, port), AnnotationHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
