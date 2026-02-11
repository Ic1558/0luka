#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from phase1a_resolver import (
    DEFAULT_ROUTING_FILE,
    ROOT,
    Phase1AResolverError,
    _parse_payload,
    _resolve_contract_path,
    gate_inbound_envelope,
    resolve_intent,
)

try:
    from jsonschema import Draft202012Validator, ValidationError, validate
except ImportError:
    class ValidationError(Exception):
        pass

    Draft202012Validator = None
    validate = None
try:
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except ImportError:
    Registry = None
    Resource = None
    DRAFT202012 = None


DEFAULT_SCHEMA_FILE = ROOT / "interface/schemas/phase1a_task_v1.json"


class Phase1AEmitError(RuntimeError):
    pass


def now_utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def now_utc_compact() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_task_id(ts_utc: str, intent: str, payload: Dict[str, Any]) -> str:
    seed = json.dumps({"ts_utc": ts_utc, "intent": intent, "payload": payload}, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"phase1a_{ts_utc.replace('-', '').replace(':', '')}_{digest}"


def derive_title(intent: str) -> str:
    return intent.replace(".", " ").strip() or "phase1a task"


def load_schema(path: Path) -> Dict[str, Any]:
    if validate is None:
        raise Phase1AEmitError("missing dependency: jsonschema (pip install jsonschema)")
    if not path.exists():
        raise Phase1AEmitError(f"schema file not found: {path}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Phase1AEmitError(f"invalid schema json: {exc}") from exc
    if not isinstance(schema, dict):
        raise Phase1AEmitError("schema must be a JSON object")
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema

    # Resolve local file refs explicitly to avoid relying on implicit external retrieval.
    target, _, frag = ref.partition("#")
    if target:
        target_path = (path.parent / target).resolve(strict=False)
        try:
            base = json.loads(target_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise Phase1AEmitError(f"schema ref load failed: {exc}") from exc
    else:
        base = schema
    if not frag:
        return base
    if not frag.startswith("/"):
        raise Phase1AEmitError(f"unsupported schema ref fragment: #{frag}")
    node: Any = base
    for token in frag.lstrip("/").split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            raise Phase1AEmitError(f"schema ref target missing: #{frag}")
    if not isinstance(node, dict):
        raise Phase1AEmitError(f"schema ref target must be object: #{frag}")
    resolved_schema = dict(node)
    if "$defs" not in resolved_schema and isinstance(base, dict) and isinstance(base.get("$defs"), dict):
        resolved_schema["$defs"] = base["$defs"]
    return resolved_schema


def _validate_task_with_registry(task: Dict[str, Any], schema_path: Path) -> None:
    # TODO(phase2): keep this local-only registry path and migrate all validators to a shared helper.
    if Draft202012Validator is None or Registry is None or Resource is None or DRAFT202012 is None:
        schema = load_schema(schema_path)
        validate(instance=task, schema=schema)
        return

    if not schema_path.exists():
        raise Phase1AEmitError(f"schema file not found: {schema_path}")
    try:
        root_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Phase1AEmitError(f"invalid schema json: {exc}") from exc

    registry = Registry()
    for candidate in sorted(schema_path.parent.glob("*.json")):
        try:
            content = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        resource = Resource(contents=content, specification=DRAFT202012)
        registry = registry.with_resource(candidate.resolve(strict=False).as_uri(), resource)
        logical_id = content.get("$id") if isinstance(content, dict) else None
        if isinstance(logical_id, str) and logical_id:
            registry = registry.with_resource(logical_id, resource)

    entry_uri = schema_path.resolve(strict=False).as_uri()
    validator = Draft202012Validator({"$ref": entry_uri}, registry=registry)
    try:
        validator.validate(task)
    except ValidationError:
        raise
    except Exception as exc:
        raise Phase1AEmitError(f"schema_validation_failed: {exc}") from exc


def resolve_inbox_root() -> Path:
    raw = os.environ.get("BRIDGE_INBOX_ROOT")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path
    return ROOT / "observability/bridge/inbox"


def make_task(
    *,
    ts_utc: str,
    task_id: str,
    origin: str,
    intent: str,
    executor: str,
    title: str,
    level: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": "phase1a_task_v1",
        "task_id": task_id,
        "ts_utc": ts_utc,
        "origin": origin,
        "intent": intent,
        "executor": executor,
        "title": title,
        "level": level,
        "payload": payload,
    }


def emit_task(task: Dict[str, Any], inbox_root: Path) -> Path:
    executor = str(task["executor"]).strip()
    target = inbox_root / executor / f"{task['task_id']}.json"
    write_json(target, task)
    return target


def write_result_and_signals(
    *,
    ts_compact: str,
    result: Dict[str, Any],
    telemetry_status: str,
    exit_code: int,
) -> Path:
    artifacts_dir = ROOT / "observability/artifacts/phase1a_emit"
    result_path = artifacts_dir / f"{ts_compact}_emit_result.json"
    write_json(result_path, result)

    telemetry = {
        "ts_utc": result.get("ts_utc"),
        "status": telemetry_status,
        "exit_code": exit_code,
        "task_id": result.get("task_id"),
        "intent": result.get("intent"),
        "executor": result.get("executor"),
        "result_path": str(result_path),
    }
    write_json(ROOT / "observability/telemetry/phase1a_emit.latest.json", telemetry)

    ledger_row = {
        "ts_utc": result.get("ts_utc"),
        "module": "phase1a_emit",
        "status": telemetry_status,
        "exit_code": exit_code,
        "task_id": result.get("task_id"),
        "intent": result.get("intent"),
        "executor": result.get("executor"),
        "result_path": str(result_path),
    }
    append_jsonl(ROOT / "observability/stl/ledger/global_beacon.jsonl", ledger_row)
    return result_path


def run(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    ts_utc = now_utc_iso()
    ts_compact = now_utc_compact()
    origin = "phase1a_ui"
    try:
        payload = _parse_payload(args.payload)
        ok, resolved = resolve_intent(
            intent=args.intent,
            payload=payload,
            contract_path=_resolve_contract_path(args.contract),
        )

        if not ok:
            result = {
                "status": "rejected",
                "ts_utc": ts_utc,
                "intent": args.intent,
                "task_id": args.task_id or "",
                "reason": resolved.get("reason"),
                "missing_fields": resolved.get("missing_fields", []),
            }
            write_result_and_signals(ts_compact=ts_compact, result=result, telemetry_status="fail", exit_code=1)
            return 1, result

        task_id = args.task_id or build_task_id(ts_utc, args.intent, payload)
        title = args.title or derive_title(args.intent)
        task = make_task(
            ts_utc=ts_utc,
            task_id=task_id,
            origin=origin,
            intent=args.intent,
            executor=resolved["executor"],
            title=title,
            level=args.level,
            payload=payload,
        )
        _validate_task_with_registry(task, _resolve_contract_path(args.schema))

        gate_in = {
            "v": "0luka.envelope/v1",
            "type": "task.request",
            "trace": {"trace_id": task_id, "ts": ts_utc},
            "source": {"actor": origin, "lane": "run"},
            "payload": {"task": {"task_id": task_id, "task_type": args.intent, "intent": args.intent, "inputs": payload}},
        }
        gated = gate_inbound_envelope(gate_in)
        task["resolved"] = gated["payload"]["task"]["resolved"]

        inbox_path = emit_task(task, resolve_inbox_root())
        inbox_ref = f"ref://observability/inbox/{resolved['executor']}/{task_id}.json"
        result = {
            "status": "emitted",
            "ts_utc": ts_utc,
            "task_id": task_id,
            "intent": args.intent,
            "executor": resolved["executor"],
            "inbox_ref": inbox_ref,
            "inbox_file": inbox_path.name,
        }
        write_result_and_signals(ts_compact=ts_compact, result=result, telemetry_status="ok", exit_code=0)
        return 0, result
    except ValidationError as exc:
        result = {
            "status": "rejected",
            "ts_utc": ts_utc,
            "intent": args.intent,
            "task_id": args.task_id or "",
            "reason": f"schema_validation_failed: {exc.message}",
        }
        write_result_and_signals(ts_compact=ts_compact, result=result, telemetry_status="fail", exit_code=1)
        return 1, result
    except (Phase1AResolverError, Phase1AEmitError) as exc:
        reason = str(exc)
        reject_prefixes = (
            "schema_validation_failed:",
            "hard_path_detected:",
            "ref_resolve_failed:",
            "invalid_resolved_resource:",
            "untrusted_resolved_inbound",
        )
        is_reject = isinstance(exc, Phase1AResolverError) and reason.startswith(reject_prefixes)
        result = {
            "status": "rejected" if is_reject else "error",
            "ts_utc": ts_utc,
            "intent": args.intent,
            "task_id": args.task_id or "",
            "reason": reason,
        }
        exit_code = 1 if is_reject else 2
        write_result_and_signals(ts_compact=ts_compact, result=result, telemetry_status="fail", exit_code=exit_code)
        return exit_code, result
    except Exception as exc:
        result = {
            "status": "error",
            "ts_utc": ts_utc,
            "intent": args.intent,
            "task_id": args.task_id or "",
            "reason": f"{exc.__class__.__name__}: {exc}",
        }
        write_result_and_signals(ts_compact=ts_compact, result=result, telemetry_status="fail", exit_code=2)
        return 2, result


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1A emit: UI natural form -> executor inbox task")
    parser.add_argument("--intent", required=True, help="routing intent (example: code.review)")
    parser.add_argument("--payload", required=True, help="payload JSON string")
    parser.add_argument("--title", default="", help="optional human title")
    parser.add_argument("--level", default="low", help="task level (default: low)")
    parser.add_argument("--task-id", default="", help="optional task id override")
    parser.add_argument("--contract", default=str(DEFAULT_ROUTING_FILE), help="routing YAML path")
    parser.add_argument("--schema", default="interface/schemas/phase1a_task_v1.json", help="task schema path")
    args = parser.parse_args()

    exit_code, result = run(args)
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
