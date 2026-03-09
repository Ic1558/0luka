#!/usr/bin/env python3
"""
feedback_loop.py — Phase D v1: observe → classify → record → escalate.

Sits ABOVE the dispatcher (reads dispatch_latest.json output only).
Never modifies dispatch path, inbox, outbox, or any QS handler.

v1 scope: observe / classify / record / escalate ONLY.
retry() and adapt() are reserved for Phase D-v2.

Lane A — Kernel Cognition.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.config import DISPATCH_LATEST, RUNTIME_ROOT

# Lane separation guard — qs.* jobs use record_only policy for non-error states.
# approval_required is NEVER escalated; it is a valid QS gate state.
QS_JOB_PREFIX = "qs."

ESCALATION_CLASSES = frozenset({"schema_violation", "hardpath", "exec_error", "circuit_open"})
RECORD_ONLY_CLASSES = frozenset({"approval_required", "policy_block", "timeout"})

FEEDBACK_REGISTRY = RUNTIME_ROOT / "state" / "feedback_registry.jsonl"
MLS_LESSONS = _REPO_ROOT / "g" / "knowledge" / "mls_lessons.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_atomic(path: Path, line: str) -> None:
    """Atomic append: read existing bytes + new line, write to .tmp, rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_bytes() if path.exists() else b""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(existing + (line + "\n").encode("utf-8"))
    os.replace(tmp, path)


class FeedbackLoop:
    """
    Phase D v1 feedback loop.
    Reads dispatch_latest.json (never writes to it).
    Writes feedback_registry.jsonl and optionally mls_lessons.jsonl.
    """

    def observe(self) -> Dict[str, Any]:
        """Read dispatch_latest.json. Returns {} on any failure."""
        try:
            return json.loads(DISPATCH_LATEST.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def classify(self, result: Dict[str, Any]) -> str:
        """
        Classify a dispatch result into one of:
          schema_violation | hardpath | timeout | exec_error | circuit_open
          | policy_block | approval_required | unknown

        approval_required is NEVER mapped to policy_block.
        This distinction is critical for QS job lifecycle correctness.
        """
        status = str(result.get("status") or "").strip().lower()
        reason = str(result.get("reason") or result.get("error") or "").lower()

        # Circuit breaker open — check before policy_block
        if "circuit_open" in reason or ("circuit" in status and "open" in status):
            return "circuit_open"

        # Approval gate — must come BEFORE policy_block
        if status in ("approval_required", "awaiting_approval") or "approval_required" in reason:
            return "approval_required"

        # Exec error / failed
        if status in ("error", "failed", "exec_error") and "schema" not in reason and "hardpath" not in reason:
            return "exec_error"

        # Schema violation
        if "schema" in reason or "schema_validation" in reason:
            return "schema_violation"

        # Hardpath violation
        if "hardpath" in reason or "hard_path" in reason or "no_hard_path" in reason:
            return "hardpath"

        # Policy block (not approval)
        if status == "rejected" and ("policy" in reason or "denied" in reason):
            return "policy_block"
        if "policy_block" in reason:
            return "policy_block"

        # Timeout
        if "timeout" in status or "timeout" in reason:
            return "timeout"

        return "unknown"

    def should_escalate(self, error_class: str, job_type: str = "") -> bool:
        """
        Return True if this error warrants escalation.

        For qs.* jobs: only exec_error and circuit_open escalate.
        approval_required is NEVER escalated (valid QS gate state, not an error).
        policy_block for qs.* jobs is record_only (gating is expected).
        """
        if error_class not in ESCALATION_CLASSES:
            return False
        if job_type.startswith(QS_JOB_PREFIX):
            # QS jobs: only these two error classes trigger escalation
            return error_class in ("exec_error", "circuit_open")
        return True

    def record(
        self,
        task_id: str,
        trace_id: str,
        error_class: str,
        action: str,
        outcome: str,
    ) -> None:
        """
        Append to feedback_registry.jsonl (atomic).
        If trace_id is present, also annotate g/knowledge/mls_lessons.jsonl
        as derivative annotation (non-fatal if it fails).
        """
        entry = {
            "ts": _utc_now(),
            "task_id": task_id or "",
            "trace_id": trace_id or "",
            "error_class": error_class,
            "action": action,
            "outcome": outcome,
        }
        _append_atomic(FEEDBACK_REGISTRY, json.dumps(entry, ensure_ascii=False))

        # Derivative annotation — only when trace_id is available
        if trace_id:
            lesson = {
                "ts": entry["ts"],
                "trace_id": trace_id,
                "lesson_type": f"feedback.{error_class}",
                "description": (
                    f"feedback loop classified {error_class}, "
                    f"action={action}, outcome={outcome}"
                ),
                "evidence_ref": f"feedback_registry:{trace_id}",
            }
            try:
                _append_atomic(MLS_LESSONS, json.dumps(lesson, ensure_ascii=False))
            except Exception:
                pass  # knowledge annotation is non-fatal

    def run_cycle(self) -> Dict[str, Any]:
        """
        v1 cycle: observe → classify → record → escalate if warranted.

        NOT in v1: retry(), adapt(), strategy switching.
        """
        result = self.observe()
        if not result:
            return {"cycle": "noop", "reason": "no_dispatch_result"}

        task_id = str(result.get("task_id") or "")
        job_type = str(result.get("job_type") or "")
        trace_id = str(result.get("trace_id") or task_id or "")
        error_class = self.classify(result)

        escalate = self.should_escalate(error_class, job_type)
        action = "escalate" if escalate else "record"

        self.record(task_id, trace_id, error_class, action, str(result.get("status") or ""))

        cycle_result: Dict[str, Any] = {
            "cycle": "complete",
            "task_id": task_id,
            "error_class": error_class,
            "action": action,
            "escalated": escalate,
        }

        if escalate:
            try:
                from core.activity_feed_guard import guarded_append_activity_feed
                guarded_append_activity_feed({
                    "action": "feedback_loop_escalation",
                    "emit_mode": "runtime_auto",
                    "task_id": task_id,
                    "error_class": error_class,
                    "job_type": job_type,
                })
            except Exception:
                pass  # feed emit failure is non-fatal

        return cycle_result
