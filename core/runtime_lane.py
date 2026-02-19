#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

try:
    import yaml
except ImportError:
    yaml = None

from core.sentry import SentryViolation, run_preflight
from core.submit import SubmitError, submit_task


class RuntimeLaneError(RuntimeError):
    pass


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _default_root() -> Path:
    raw = os.environ.get("ROOT")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _fixture_path(root: Path) -> Path:
    return root / "modules" / "nlp_control_plane" / "tests" / "phase9_vectors_v0.yaml"


def _load_fixture(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeLaneError("pyyaml_missing")
    if not path.exists():
        raise RuntimeLaneError(f"fixture_missing:{path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeLaneError("fixture_invalid")
    return data


def _normalize_input(raw: str) -> str:
    return raw.strip()


def _match_vectors(data: dict[str, Any], text: str) -> tuple[str, dict[str, Any]]:
    vectors = data.get("vectors") if isinstance(data.get("vectors"), list) else []
    matches = [v for v in vectors if isinstance(v, dict) and str(v.get("input", "")).strip() == text]
    if len(matches) > 1:
        return "needs_clarification", {"reason": "ambiguous_mapping"}
    if len(matches) == 1:
        v = matches[0]
        return "ok", {
            "intent": str(v.get("expected_intent", "")),
            "slots": v.get("required_slots", {}) if isinstance(v.get("required_slots"), dict) else {},
            "vector_id": str(v.get("id", "")),
        }

    fail_closed = data.get("fail_closed_cases") if isinstance(data.get("fail_closed_cases"), list) else []
    for row in fail_closed:
        if isinstance(row, dict) and str(row.get("input", "")).strip() == text:
            return "needs_clarification", {
                "reason": str(row.get("reason", "needs_clarification")),
                "vector_id": str(row.get("id", "")),
            }
    return "needs_clarification", {"reason": "no_exact_match"}


def _is_root_relative(path_value: str) -> bool:
    p = str(path_value or "").strip()
    if not p:
        return False
    if p.startswith("/") or p.startswith("~"):
        return False
    return ".." not in Path(p).parts


def _normalize_command(command: str, root: Path) -> str:
    return str(command).replace("${ROOT}", str(root))


def _enforce_invariants(intent: str, slots: Dict[str, Any], fixture: Dict[str, Any], *, root: Path) -> None:
    allowed = (
        ((fixture.get("taxonomy") or {}).get("allowed_intents"))
        if isinstance(fixture.get("taxonomy"), dict)
        else []
    )
    if not isinstance(allowed, list) or intent not in allowed:
        raise RuntimeLaneError("intent_not_in_taxonomy")

    path_intents = {"ops.write_text", "ops.append_text", "ops.mkdir", "ops.list_dir", "ops.read_text"}
    if intent in path_intents:
        path = str(slots.get("path", ""))
        if not _is_root_relative(path):
            raise RuntimeLaneError("path_policy_violation")

    if intent == "ops.run_command_safe":
        if str(slots.get("allowlist_id", "")) != "cmd.safe.v0":
            raise RuntimeLaneError("command_allowlist_id_mismatch")
        command = str(slots.get("command", "")).strip()
        if command != "git status":
            raise RuntimeLaneError("command_not_allowlisted")

    if intent == "audit.lint_activity_feed":
        if str(slots.get("command_id", "")) != "activity_feed_linter.canonical":
            raise RuntimeLaneError("command_id_mismatch")
        command = str(slots.get("command", "")).strip()
        canonical = "cd ${ROOT} && bash ${ROOT}/tools/ops/lint_safe.zsh"
        if command != canonical:
            raise RuntimeLaneError("command_template_mismatch")
        # Current submit gate run-command allowlist does not include this command.
        raise RuntimeLaneError("runtime_command_not_allowlisted")

    if intent == "audit.run_pytest":
        command = str(slots.get("command", "")).strip()
        canonical = "cd ${ROOT} && bash ${ROOT}/tools/ops/pytest_safe.zsh"
        if command != canonical:
            raise RuntimeLaneError("command_template_mismatch")

    if intent == "kernel.enqueue_task":
        task = slots.get("task")
        if not isinstance(task, dict):
            raise RuntimeLaneError("missing_task_slot")
        ops = task.get("ops")
        if not isinstance(ops, list) or not ops:
            raise RuntimeLaneError("missing_task_ops")
        for op in ops:
            if not isinstance(op, dict):
                raise RuntimeLaneError("invalid_task_op")
            target_path = str(op.get("target_path", ""))
            if target_path and not _is_root_relative(target_path):
                raise RuntimeLaneError("path_policy_violation")

    if intent == "kernel.status.dispatcher":
        if str(slots.get("probe", "")) != "launchd.dispatcher.status":
            raise RuntimeLaneError("probe_template_mismatch")

    _ = root


def _build_taskspec(intent: str, slots: Dict[str, Any], *, root: Path) -> Dict[str, Any]:
    base = {
        "schema_version": "clec.v1",
        "ts_utc": _utc_now(),
        "author": "codex",
        "call_sign": "[Lisa]",
        "root": "${ROOT}",
        "intent": intent,
        "verify": [],
    }

    if intent == "ops.write_text":
        ops = [{"op_id": "op1", "type": "write_text", "target_path": slots["path"], "content": slots["content"]}]
    elif intent == "ops.append_text":
        raise RuntimeLaneError("intent_not_runtime_enabled")
    elif intent == "ops.mkdir":
        ops = [{"op_id": "op1", "type": "mkdir", "target_path": slots["path"]}]
    elif intent == "ops.list_dir":
        raise RuntimeLaneError("intent_not_runtime_enabled")
    elif intent == "ops.read_text":
        raise RuntimeLaneError("intent_not_runtime_enabled")
    elif intent == "ops.run_command_safe":
        ops = [{"op_id": "op1", "type": "run", "command": slots["command"]}]
    elif intent == "audit.lint_activity_feed":
        ops = [{"op_id": "op1", "type": "run", "command": _normalize_command(str(slots["command"]), root)}]
    elif intent == "audit.run_pytest":
        ops = [{"op_id": "op1", "type": "run", "command": _normalize_command(str(slots["command"]), root)}]
    elif intent == "kernel.enqueue_task":
        task = dict(slots["task"])
        task.setdefault("schema_version", "clec.v1")
        task.setdefault("verify", [])
        task.setdefault("author", "codex")
        task.setdefault("call_sign", "[Lisa]")
        task.setdefault("root", "${ROOT}")
        task.setdefault("ts_utc", _utc_now())
        task.setdefault("intent", intent)
        normalized_ops = []
        for idx, op in enumerate(task.get("ops", []), start=1):
            if not isinstance(op, dict):
                continue
            row = dict(op)
            row.setdefault("op_id", f"op{idx}")
            normalized_ops.append(row)
        task["ops"] = normalized_ops
        return task
    elif intent == "kernel.status.dispatcher":
        raise RuntimeLaneError("intent_not_runtime_enabled")
    else:
        raise RuntimeLaneError("intent_not_supported")

    out = dict(base)
    out["ops"] = ops
    return out


def submit_from_text(
    text: str,
    *,
    root: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Dict[str, Any]:
    text = _normalize_input(text)
    lane_root = (root or _default_root()).resolve()
    trace = f"trace_{int(time.time() * 1000)}"

    try:
        run_preflight(root=lane_root, require_activity_feed=True, probe_dispatcher=True, runner=runner)
    except SentryViolation as exc:
        return {"ok": False, "error": f"sentry_violation:{exc}", "trace": trace}

    if not text:
        return {"ok": False, "expected_result": "needs_clarification", "reason": "empty_input", "trace": trace}

    try:
        fixture = _load_fixture(_fixture_path(lane_root))
    except RuntimeLaneError as exc:
        return {"ok": False, "error": str(exc), "trace": trace}

    status, payload = _match_vectors(fixture, text)
    if status != "ok":
        return {
            "ok": False,
            "expected_result": "needs_clarification",
            "reason": payload.get("reason", "needs_clarification"),
            "vector_id": payload.get("vector_id"),
            "trace": trace,
        }

    intent = str(payload["intent"])
    slots = payload["slots"] if isinstance(payload["slots"], dict) else {}
    vector_id = payload.get("vector_id")

    try:
        _enforce_invariants(intent, slots, fixture, root=lane_root)
        task = _build_taskspec(intent, slots, root=lane_root)
    except RuntimeLaneError as exc:
        return {
            "ok": False,
            "expected_result": "needs_clarification",
            "reason": str(exc),
            "vector_id": vector_id,
            "trace": trace,
        }

    try:
        receipt = submit_task(task)
    except SubmitError as exc:
        return {"ok": False, "error": f"submit_error:{exc}", "trace": trace, "vector_id": vector_id}

    return {
        "ok": True,
        "status": "submit_accepted",
        "intent": intent,
        "vector_id": vector_id,
        "task_spec": task,
        "receipt": receipt,
        "trace": trace,
    }


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Runtime lane adapter v0 (submit only)")
    parser.add_argument("--input", type=str, help="NLP input text")
    args = parser.parse_args()
    text = _normalize_input(args.input or "")
    if not text:
        text = _normalize_input(sys.stdin.read())

    result = submit_from_text(text)
    print(json.dumps(result, ensure_ascii=False))
    if result.get("ok") is True:
        return 0
    if result.get("expected_result") == "needs_clarification":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
