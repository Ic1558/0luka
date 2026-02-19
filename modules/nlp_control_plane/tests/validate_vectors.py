#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

DEFAULT_FIXTURE = Path("/Users/icmini/0luka/modules/nlp_control_plane/tests/phase9_vectors_v0.yaml")
CANONICAL_LINTER_CMD = (
    "cd /Users/icmini/0luka && python3 /Users/icmini/0luka/tools/ops/activity_feed_linter.py --json"
)


class Violation:
    def __init__(self, entry_id: str, rule: str, detail: str) -> None:
        self.entry_id = entry_id
        self.rule = rule
        self.detail = detail

    def render(self) -> str:
        return f"{self.entry_id} [{self.rule}] {self.detail}"


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _has_forbidden_path(path: str) -> str | None:
    if not path.strip():
        return "empty_path"
    p = Path(path)
    if p.is_absolute() or path.startswith("/"):
        return "absolute_path"
    if any(part == ".." for part in p.parts):
        return "traversal_path"
    return None


def _add(vios: list[Violation], entry_id: str, rule: str, detail: str) -> None:
    vios.append(Violation(entry_id, rule, detail))


def validate_fixture(fixture_path: Path) -> tuple[bool, list[Violation], int, int]:
    vios: list[Violation] = []

    if yaml is None:
        _add(vios, "~root", "yaml_dependency", "pyyaml is required")
        return False, vios, 0, 0

    if not fixture_path.exists():
        _add(vios, "~root", "fixture_exists", f"missing fixture: {fixture_path}")
        return False, vios, 0, 0

    try:
        data = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _add(vios, "~root", "yaml_parse", str(exc))
        return False, vios, 0, 0

    if not isinstance(data, dict):
        _add(vios, "~root", "root_mapping", "fixture must be a mapping")
        return False, vios, 0, 0

    required_top = ["version", "root", "taxonomy", "policy", "vectors", "fail_closed_cases"]
    for key in required_top:
        if key not in data:
            _add(vios, "~root", "top_level_key", f"missing key: {key}")

    version = data.get("version")
    if not _is_non_empty_str(version):
        _add(vios, "~root", "version", "version must be a non-empty string")

    root = data.get("root")
    if not _is_non_empty_str(root):
        _add(vios, "~root", "root", "root must be a non-empty string")

    taxonomy = data.get("taxonomy")
    allowed_intents: list[str] = []
    if not isinstance(taxonomy, dict):
        _add(vios, "~root", "taxonomy", "taxonomy must be a mapping")
    else:
        allowed = taxonomy.get("allowed_intents")
        if not isinstance(allowed, list) or not allowed or not all(_is_non_empty_str(x) for x in allowed):
            _add(vios, "~root", "taxonomy.allowed_intents", "must be a non-empty list of strings")
        else:
            allowed_intents = [str(x) for x in allowed]

    policy = data.get("policy")
    path_policy = {}
    command_policy = {}
    if not isinstance(policy, dict):
        _add(vios, "~root", "policy", "policy must be a mapping")
    else:
        path_policy = policy.get("path_policy")
        command_policy = policy.get("command_policy")
        if not isinstance(path_policy, dict):
            _add(vios, "~root", "policy.path_policy", "must be a mapping")
            path_policy = {}
        if not isinstance(command_policy, dict):
            _add(vios, "~root", "policy.command_policy", "must be a mapping")
            command_policy = {}

    if path_policy.get("root_relative_only") is not True:
        _add(vios, "~root", "path_policy.root_relative_only", "must be true")
    if path_policy.get("forbid_traversal") is not True:
        _add(vios, "~root", "path_policy.forbid_traversal", "must be true")
    if path_policy.get("forbid_absolute") is not True:
        _add(vios, "~root", "path_policy.forbid_absolute", "must be true")

    if command_policy.get("allowlist_id") != "cmd.safe.v0":
        _add(vios, "~root", "command_policy.allowlist_id", "must equal cmd.safe.v0")

    vectors = data.get("vectors")
    n_vectors = len(vectors) if isinstance(vectors, list) else 0
    if not isinstance(vectors, list) or not vectors:
        _add(vios, "~root", "vectors", "vectors must be a non-empty list")
        vectors = []

    fail_closed = data.get("fail_closed_cases")
    n_fail_closed = len(fail_closed) if isinstance(fail_closed, list) else 0
    if not isinstance(fail_closed, list):
        _add(vios, "~root", "fail_closed_cases", "fail_closed_cases must be a list")
        fail_closed = []

    seen_vector_ids: set[str] = set()
    for row in vectors:
        entry_id = "<missing-id>"
        if not isinstance(row, dict):
            _add(vios, entry_id, "vector.mapping", "vector entry must be a mapping")
            continue
        entry_id = str(row.get("id", "<missing-id>"))

        for key in ("id", "input", "expected_intent", "required_slots", "expected_result"):
            if key not in row:
                _add(vios, entry_id, "vector.required_key", f"missing key: {key}")

        if not _is_non_empty_str(row.get("id")):
            _add(vios, entry_id, "vector.id", "id must be non-empty string")
        else:
            if entry_id in seen_vector_ids:
                _add(vios, entry_id, "vector.id_unique", "duplicate vector id")
            seen_vector_ids.add(entry_id)

        if not _is_non_empty_str(row.get("input")):
            _add(vios, entry_id, "vector.input", "input must be non-empty string")

        intent = row.get("expected_intent")
        if not _is_non_empty_str(intent):
            _add(vios, entry_id, "vector.expected_intent", "expected_intent must be non-empty string")
            intent = ""
        elif allowed_intents and intent not in allowed_intents:
            _add(vios, entry_id, "taxonomy.membership", f"intent not allowed: {intent}")

        slots = row.get("required_slots")
        if not isinstance(slots, dict):
            _add(vios, entry_id, "vector.required_slots", "required_slots must be a mapping")
            slots = {}

        if not _is_non_empty_str(row.get("expected_result")):
            _add(vios, entry_id, "vector.expected_result", "expected_result must be non-empty string")

        def _check_path_slot(slot_name: str, slot_value: Any) -> None:
            if not _is_non_empty_str(slot_value):
                _add(vios, entry_id, f"slot.{slot_name}", f"{slot_name} must be non-empty string")
                return
            err = _has_forbidden_path(str(slot_value))
            if err:
                _add(vios, entry_id, f"path_policy.{slot_name}", err)

        if intent == "ops.write_text":
            if "path" not in slots:
                _add(vios, entry_id, "slot.path", "missing path")
            if "content" not in slots:
                _add(vios, entry_id, "slot.content", "missing content")
            _check_path_slot("path", slots.get("path"))
            if not _is_non_empty_str(slots.get("content")):
                _add(vios, entry_id, "slot.content", "content must be non-empty string")

        elif intent == "ops.append_text":
            if "path" not in slots:
                _add(vios, entry_id, "slot.path", "missing path")
            if "content" not in slots:
                _add(vios, entry_id, "slot.content", "missing content")
            _check_path_slot("path", slots.get("path"))
            if not _is_non_empty_str(slots.get("content")):
                _add(vios, entry_id, "slot.content", "content must be non-empty string")

        elif intent in {"ops.mkdir", "ops.list_dir", "ops.read_text"}:
            if "path" not in slots:
                _add(vios, entry_id, "slot.path", "missing path")
            _check_path_slot("path", slots.get("path"))

        elif intent == "ops.run_command_safe":
            if not _is_non_empty_str(slots.get("command")):
                _add(vios, entry_id, "slot.command", "command must be non-empty string")
            if slots.get("allowlist_id") != "cmd.safe.v0":
                _add(vios, entry_id, "slot.allowlist_id", "allowlist_id must equal cmd.safe.v0")

        elif intent == "audit.lint_activity_feed":
            if slots.get("command_id") != "activity_feed_linter.canonical":
                _add(vios, entry_id, "slot.command_id", "command_id must equal activity_feed_linter.canonical")
            cmd = slots.get("command")
            if not _is_non_empty_str(cmd):
                _add(vios, entry_id, "slot.command", "command must be non-empty string")
            elif CANONICAL_LINTER_CMD not in str(cmd):
                _add(vios, entry_id, "slot.command", "command must contain canonical linter command")

        elif intent == "audit.run_pytest":
            if slots.get("command") != "python3 -m pytest tests/ -q":
                _add(vios, entry_id, "slot.command", "command must equal 'python3 -m pytest tests/ -q'")

        elif intent == "kernel.enqueue_task":
            task = slots.get("task")
            if not isinstance(task, dict):
                _add(vios, entry_id, "slot.task", "task must be a mapping")
            else:
                if task.get("schema_version") != "clec.v1":
                    _add(vios, entry_id, "slot.task.schema_version", "task.schema_version must equal clec.v1")
                if not _is_non_empty_str(task.get("intent")):
                    _add(vios, entry_id, "slot.task.intent", "task.intent must be non-empty string")
                ops = task.get("ops")
                if not isinstance(ops, list) or not ops:
                    _add(vios, entry_id, "slot.task.ops", "task.ops must be a non-empty list")
                else:
                    for idx, op in enumerate(ops):
                        if not isinstance(op, dict):
                            _add(vios, entry_id, "slot.task.ops.item", f"op index {idx} must be mapping")
                            continue
                        if not _is_non_empty_str(op.get("type")):
                            _add(vios, entry_id, "slot.task.ops.type", f"op index {idx} missing type")
                        if op.get("type") == "write_text":
                            tp = op.get("target_path")
                            if not _is_non_empty_str(tp):
                                _add(vios, entry_id, "slot.task.ops.target_path", f"op index {idx} missing target_path")
                            else:
                                err = _has_forbidden_path(str(tp))
                                if err:
                                    _add(vios, entry_id, "path_policy.task.ops.target_path", f"op index {idx}: {err}")
                            if not _is_non_empty_str(op.get("content")):
                                _add(vios, entry_id, "slot.task.ops.content", f"op index {idx} missing content")

        elif intent == "kernel.status.dispatcher":
            if slots.get("probe") != "launchd.dispatcher.status":
                _add(vios, entry_id, "slot.probe", "probe must equal launchd.dispatcher.status")

    seen_fail_ids: set[str] = set()
    for row in fail_closed:
        entry_id = "<missing-id>"
        if not isinstance(row, dict):
            _add(vios, entry_id, "fail_closed.mapping", "fail_closed entry must be a mapping")
            continue
        entry_id = str(row.get("id", "<missing-id>"))
        if not _is_non_empty_str(row.get("id")):
            _add(vios, entry_id, "fail_closed.id", "id must be non-empty string")
        else:
            if entry_id in seen_fail_ids:
                _add(vios, entry_id, "fail_closed.id_unique", "duplicate fail_closed id")
            seen_fail_ids.add(entry_id)
        if not _is_non_empty_str(row.get("input")):
            _add(vios, entry_id, "fail_closed.input", "input must be non-empty string")
        if not _is_non_empty_str(row.get("reason")):
            _add(vios, entry_id, "fail_closed.reason", "reason must be non-empty string")
        if row.get("expected_result") != "needs_clarification":
            _add(vios, entry_id, "fail_closed.expected_result", "expected_result must equal needs_clarification")

    vios.sort(key=lambda v: (v.entry_id, v.rule, v.detail))
    return len(vios) == 0, vios, n_vectors, n_fail_closed


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 9 Linguist vectors fixture")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="Path to fixture YAML")
    args = parser.parse_args()

    ok, violations, n_vectors, n_fail_closed = validate_fixture(args.fixture)
    if ok:
        print(f"PASS: {n_vectors} vectors, {n_fail_closed} fail_closed, ok=true")
        return 0

    for row in violations:
        print(row.render())
    print(f"FAIL: {len(violations)} violations, ok=false")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
