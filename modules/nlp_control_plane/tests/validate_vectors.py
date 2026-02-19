#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = os.environ.get("ROOT") or str(Path(__file__).resolve().parents[3])
DEFAULT_FIXTURE = Path(__file__).resolve().parent / "phase9_vectors_v0.yaml"
CANONICAL_LINTER_CMD = f'cd {ROOT} && python3 {ROOT}/tools/ops/activity_feed_linter.py --json'


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _path_error(path: Any) -> str | None:
    if not _is_non_empty_str(path):
        return "empty"
    raw = str(path)
    p = Path(raw)
    if p.is_absolute() or raw.startswith("/"):
        return "absolute"
    if any(part == ".." for part in p.parts):
        return "traversal"
    return None


def validate_fixture(fixture_path: Path) -> dict[str, Any]:
    violations: list[dict[str, str]] = []

    def add(entry_id: str, rule: str, detail: str) -> None:
        violations.append({"id": entry_id, "rule": rule, "detail": detail})

    if yaml is None:
        add("~root", "yaml_dependency", "pyyaml is required")
        return {"ok": False, "counts": {"vectors": 0, "fail_closed": 0}, "violations": violations}

    if not fixture_path.exists():
        add("~root", "fixture_exists", f"missing fixture: {fixture_path}")
        return {"ok": False, "counts": {"vectors": 0, "fail_closed": 0}, "violations": violations}

    try:
        data = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    except Exception as exc:
        add("~root", "yaml_parse", str(exc))
        return {"ok": False, "counts": {"vectors": 0, "fail_closed": 0}, "violations": violations}

    if not isinstance(data, dict):
        add("~root", "root_mapping", "fixture must be a mapping")
        return {"ok": False, "counts": {"vectors": 0, "fail_closed": 0}, "violations": violations}

    for k in ("version", "root", "taxonomy", "policy", "vectors", "fail_closed_cases"):
        if k not in data:
            add("~root", "top_level_key", f"missing key: {k}")

    if not _is_non_empty_str(data.get("version")):
        add("~root", "version", "version must be non-empty string")
    if not _is_non_empty_str(data.get("root")):
        add("~root", "root", "root must be non-empty string")

    taxonomy = data.get("taxonomy")
    allowed_intents: list[str] = []
    if not isinstance(taxonomy, dict):
        add("~root", "taxonomy", "taxonomy must be a mapping")
    else:
        intents = taxonomy.get("allowed_intents")
        if not isinstance(intents, list) or not intents or not all(_is_non_empty_str(x) for x in intents):
            add("~root", "taxonomy.allowed_intents", "must be non-empty list of strings")
        else:
            allowed_intents = [str(x) for x in intents]

    policy = data.get("policy")
    path_policy: dict[str, Any] = {}
    command_policy: dict[str, Any] = {}
    if not isinstance(policy, dict):
        add("~root", "policy", "policy must be a mapping")
    else:
        path_policy = policy.get("path_policy") if isinstance(policy.get("path_policy"), dict) else {}
        command_policy = policy.get("command_policy") if isinstance(policy.get("command_policy"), dict) else {}
        if not path_policy:
            add("~root", "policy.path_policy", "must be a mapping")
        if not command_policy:
            add("~root", "policy.command_policy", "must be a mapping")

    if path_policy.get("root_relative_only") is not True:
        add("~root", "path_policy.root_relative_only", "must be true")
    if path_policy.get("forbid_traversal") is not True:
        add("~root", "path_policy.forbid_traversal", "must be true")
    if path_policy.get("forbid_absolute") is not True:
        add("~root", "path_policy.forbid_absolute", "must be true")
    if command_policy.get("allowlist_id") != "cmd.safe.v0":
        add("~root", "command_policy.allowlist_id", "must equal cmd.safe.v0")

    vectors = data.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        add("~root", "vectors", "must be non-empty list")
        vectors = []

    fail_closed_cases = data.get("fail_closed_cases")
    if not isinstance(fail_closed_cases, list):
        add("~root", "fail_closed_cases", "must be list")
        fail_closed_cases = []

    seen_ids: set[str] = set()
    for v in vectors:
        vid = str(v.get("id", "<missing-id>")) if isinstance(v, dict) else "<missing-id>"
        if not isinstance(v, dict):
            add(vid, "vector.mapping", "must be mapping")
            continue

        for k in ("id", "input", "expected_intent", "required_slots", "expected_result"):
            if k not in v:
                add(vid, "vector.required_key", f"missing key: {k}")

        if not _is_non_empty_str(v.get("id")):
            add(vid, "vector.id", "id must be non-empty string")
        elif vid in seen_ids:
            add(vid, "vector.id_unique", "duplicate id")
        else:
            seen_ids.add(vid)

        if not _is_non_empty_str(v.get("input")):
            add(vid, "vector.input", "input must be non-empty string")

        intent = v.get("expected_intent")
        if not _is_non_empty_str(intent):
            add(vid, "vector.expected_intent", "must be non-empty string")
            intent = ""
        elif intent not in allowed_intents:
            add(vid, "taxonomy.membership", f"intent not allowed: {intent}")

        slots = v.get("required_slots")
        if not isinstance(slots, dict):
            add(vid, "vector.required_slots", "must be mapping")
            slots = {}

        if not _is_non_empty_str(v.get("expected_result")):
            add(vid, "vector.expected_result", "must be non-empty string")

        if intent in {"ops.write_text", "ops.append_text", "ops.mkdir", "ops.list_dir", "ops.read_text"}:
            if "path" not in slots:
                add(vid, "slot.path", "missing path")
            err = _path_error(slots.get("path"))
            if err:
                add(vid, "path_policy.path", err)
            if intent in {"ops.write_text", "ops.append_text"} and not _is_non_empty_str(slots.get("content")):
                add(vid, "slot.content", "missing content")

        if intent == "ops.run_command_safe":
            if not _is_non_empty_str(slots.get("command")):
                add(vid, "slot.command", "missing command")
            if slots.get("allowlist_id") != "cmd.safe.v0":
                add(vid, "slot.allowlist_id", "must equal cmd.safe.v0")

        if intent == "audit.lint_activity_feed":
            if slots.get("command_id") != "activity_feed_linter.canonical":
                add(vid, "slot.command_id", "must equal activity_feed_linter.canonical")
            if slots.get("command") != "cd ${ROOT} && python3 ${ROOT}/tools/ops/activity_feed_linter.py --json":
                add(vid, "slot.command", "must match canonical fixture command")

        if intent == "audit.run_pytest":
            if slots.get("command") != "python3 -m pytest tests/ -q":
                add(vid, "slot.command", "must equal python3 -m pytest tests/ -q")

        if intent == "kernel.enqueue_task":
            task = slots.get("task")
            if not isinstance(task, dict):
                add(vid, "slot.task", "must be mapping")
            else:
                if task.get("schema_version") != "clec.v1":
                    add(vid, "slot.task.schema_version", "must equal clec.v1")
                if not _is_non_empty_str(task.get("intent")):
                    add(vid, "slot.task.intent", "must be non-empty string")
                ops = task.get("ops")
                if not isinstance(ops, list) or not ops:
                    add(vid, "slot.task.ops", "must be non-empty list")
                else:
                    for idx, op in enumerate(ops):
                        if not isinstance(op, dict):
                            add(vid, "slot.task.ops.item", f"op index {idx} must be mapping")
                            continue
                        if not _is_non_empty_str(op.get("type")):
                            add(vid, "slot.task.ops.type", f"op index {idx} missing type")
                        if op.get("type") == "write_text":
                            err = _path_error(op.get("target_path"))
                            if err:
                                add(vid, "path_policy.target_path", f"op index {idx}: {err}")
                            if not _is_non_empty_str(op.get("content")):
                                add(vid, "slot.task.ops.content", f"op index {idx} missing content")

        if intent == "kernel.status.dispatcher":
            if slots.get("probe") != "launchd.dispatcher.status":
                add(vid, "slot.probe", "must equal launchd.dispatcher.status")

    fail_seen: set[str] = set()
    for row in fail_closed_cases:
        fid = str(row.get("id", "<missing-id>")) if isinstance(row, dict) else "<missing-id>"
        if not isinstance(row, dict):
            add(fid, "fail_closed.mapping", "must be mapping")
            continue
        if not _is_non_empty_str(row.get("id")):
            add(fid, "fail_closed.id", "must be non-empty string")
        elif fid in fail_seen:
            add(fid, "fail_closed.id_unique", "duplicate id")
        else:
            fail_seen.add(fid)
        if not _is_non_empty_str(row.get("input")):
            add(fid, "fail_closed.input", "must be non-empty string")
        if not _is_non_empty_str(row.get("reason")):
            add(fid, "fail_closed.reason", "must be non-empty string")
        if row.get("expected_result") != "needs_clarification":
            add(fid, "fail_closed.expected_result", "must equal needs_clarification")

    violations.sort(key=lambda x: (x["id"], x["rule"], x["detail"]))
    return {
        "ok": len(violations) == 0,
        "counts": {"vectors": len(vectors), "fail_closed": len(fail_closed_cases)},
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate phase9 vectors fixture")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()

    res = validate_fixture(args.fixture)
    if res["ok"]:
        print(f"PASS: {res['counts']['vectors']} vectors, {res['counts']['fail_closed']} fail_closed, ok=true")
        return 0

    for v in res["violations"]:
        print(f"{v['id']} [{v['rule']}] {v['detail']}")
    print(f"FAIL: {len(res['violations'])} violations, ok=false")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
