#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import fnmatch
import json
import os
import shlex
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None
try:
    from jsonschema import Draft202012Validator, ValidationError, validate
except ImportError:
    ValidationError = Exception  # type: ignore[assignment]
    Draft202012Validator = None
    validate = None
try:
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except ImportError:
    Registry = None
    Resource = None
    DRAFT202012 = None

try:
    from core.ref_resolver import resolve_ref
    from core.verify.no_hardpath_guard import find_hardpath_violations
except ImportError:
    from ref_resolver import resolve_ref
    from verify.no_hardpath_guard import find_hardpath_violations


ROOT = Path(os.environ.get("ROOT") or Path(__file__).resolve().parents[1])
DEFAULT_ROUTING_FILE = ROOT / "interface/schemas/phase1a_routing_v1.yaml"
DEFAULT_COMBINED_SCHEMA = ROOT / "core/contracts/v1/0luka_schemas.json"
DEFAULT_CLEC_SCHEMA = ROOT / "interface/schemas/clec_v1.yaml"
ALLOWED_CLEC_COMMANDS = [
    "pytest",
    "python3 -m pytest",
    "python3 core/verify/*.py",
    "git status",
    "git diff",
]


class Phase1AResolverError(RuntimeError):
    pass


def _load_combined_schema(path: Path) -> Dict[str, Any]:
    if validate is None:
        raise Phase1AResolverError("missing dependency: jsonschema (pip install jsonschema)")
    if not path.exists():
        raise Phase1AResolverError(f"combined schema not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Phase1AResolverError(f"invalid combined schema json: {exc}") from exc
    if not isinstance(data, dict):
        raise Phase1AResolverError("combined schema must be an object")
    return data


def _load_contract(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise Phase1AResolverError("missing dependency: pyyaml (pip install pyyaml)")
    if not path.exists():
        raise Phase1AResolverError(f"routing file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception as exc:
        raise Phase1AResolverError(f"failed to parse routing file: {exc}") from exc

    if not isinstance(data, dict):
        raise Phase1AResolverError("routing contract must be a mapping")
    if not isinstance(data.get("defaults"), dict):
        raise Phase1AResolverError("routing contract missing defaults mapping")
    if not isinstance(data.get("routes"), dict):
        raise Phase1AResolverError("routing contract missing routes mapping")
    return data


def _required_missing(route: Dict[str, Any], payload: Optional[Dict[str, Any]]) -> List[str]:
    required = route.get("required_payload") or []
    if not required:
        return []
    if not isinstance(required, list):
        return ["required_payload_invalid"]
    payload = payload or {}
    if not isinstance(payload, dict):
        return list(required)
    return [field for field in required if field not in payload]


def resolve_intent(
    intent: str,
    payload: Optional[Dict[str, Any]] = None,
    contract_path: Path = DEFAULT_ROUTING_FILE,
) -> Tuple[bool, Dict[str, Any]]:
    contract = _load_contract(contract_path)
    defaults = contract["defaults"]
    routes = contract["routes"]

    route = routes.get(intent, {})
    if route and not isinstance(route, dict):
        return False, {"status": "error", "reason": "route_invalid", "intent": intent}

    missing = _required_missing(route, payload)
    if missing:
        return (
            False,
            {
                "status": "rejected",
                "reason": "payload_missing_fields",
                "intent": intent,
                "missing_fields": missing,
            },
        )

    return (
        True,
        {
            "status": "resolved",
            "intent": intent,
            "executor": route.get("executor", defaults.get("executor")),
            "lane": route.get("lane", defaults.get("lane")),
            "contract": contract.get("contract", "phase1a"),
            "version": contract.get("version"),
        },
    )


def _parse_payload(raw_payload: str) -> Dict[str, Any]:
    try:
        decoded = json.loads(raw_payload)
    except Exception as exc:
        raise Phase1AResolverError(f"invalid payload json: {exc}") from exc
    if not isinstance(decoded, dict):
        raise Phase1AResolverError("payload must decode to a JSON object")
    return decoded


def _resolve_contract_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return ROOT / path


def _extract_refs(task: Dict[str, Any]) -> List[str]:
    inputs = task.get("inputs") or {}
    refs: List[str] = []
    if isinstance(inputs.get("refs"), list):
        for ref in inputs["refs"]:
            if isinstance(ref, str):
                refs.append(ref)
    if isinstance(inputs.get("files"), list):
        for item in inputs["files"]:
            if isinstance(item, dict) and isinstance(item.get("ref"), str):
                refs.append(item["ref"])
    return refs


def _validate_envelope(envelope: Dict[str, Any], schema_path: Path) -> None:
    schema = _load_combined_schema(schema_path)
    envelope_schema = {"$schema": schema.get("$schema"), "$ref": str(schema_path.resolve(strict=False).as_uri()) + "#/$defs/envelope"}
    if Draft202012Validator is None or Registry is None or Resource is None or DRAFT202012 is None:
        # TODO(phase2): migrate all jsonschema validation to a shared local-only Registry helper.
        validate(instance=envelope, schema=envelope_schema)
        return
    resource = Resource(contents=schema, specification=DRAFT202012)
    registry = Registry().with_resource(schema_path.resolve(strict=False).as_uri(), resource)
    logical_id = schema.get("$id")
    if isinstance(logical_id, str) and logical_id:
        registry = registry.with_resource(logical_id, resource)
    Draft202012Validator(envelope_schema, registry=registry).validate(envelope)


def _load_clec_schema(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise Phase1AResolverError("missing dependency: pyyaml (pip install pyyaml)")
    if validate is None:
        raise Phase1AResolverError("missing dependency: jsonschema (pip install jsonschema)")
    if not path.exists():
        raise Phase1AResolverError(f"clec schema not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise Phase1AResolverError(f"failed to parse clec schema: {exc}") from exc
    if not isinstance(data, dict):
        raise Phase1AResolverError("clec schema must be an object")
    return data


def _command_allowed(command: str) -> bool:
    normalized = " ".join(shlex.split(command.strip()))
    if not normalized:
        return False
    for pattern in ALLOWED_CLEC_COMMANDS:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def _validate_clec_verify(verify: Any) -> None:
    if verify is None:
        return
    if not isinstance(verify, list):
        raise Phase1AResolverError("clec verify must be an array")
    for idx, item in enumerate(verify):
        if not isinstance(item, dict):
            raise Phase1AResolverError(f"clec verify item must be object: index={idx}")
        check = item.get("check")
        target = item.get("target")
        if check not in {"gate.fs.exists", "gate.test.run", "gate.hash.present"}:
            raise Phase1AResolverError(f"clec unsupported verify check: index={idx}")
        if not isinstance(target, str) or not target.strip():
            raise Phase1AResolverError(f"clec verify target missing: index={idx}")
        if check == "gate.test.run":
            command = item.get("command", "")
            if not isinstance(command, str) or not _command_allowed(command):
                raise Phase1AResolverError(f"clec unauthorized verify command: index={idx}")


def _validate_clec_task(task: Dict[str, Any]) -> None:
    schema = _load_clec_schema(DEFAULT_CLEC_SCHEMA)
    try:
        validate(instance=task, schema=schema)
    except ValidationError as exc:
        raise Phase1AResolverError(f"clec_schema_validation_failed: {exc.message}") from exc

    ops = task.get("ops")
    if not isinstance(ops, list) or not ops:
        raise Phase1AResolverError("clec ops missing")
    allowed_types = {"mkdir", "write_text", "copy", "patch_apply", "run"}
    for idx, op in enumerate(ops):
        if not isinstance(op, dict):
            raise Phase1AResolverError(f"clec op must be object: index={idx}")
        op_type = op.get("type")
        if op_type not in allowed_types:
            raise Phase1AResolverError(f"clec unsupported op type: index={idx}")
        if op_type == "run":
            command = op.get("command", "")
            if not isinstance(command, str) or not _command_allowed(command):
                raise Phase1AResolverError(f"clec unauthorized run command: index={idx}")

    _validate_clec_verify(task.get("verify"))


def gate_inbound_envelope(
    envelope: Dict[str, Any],
    *,
    schema_path: Optional[str] = None,
    ref_map_path: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(envelope, dict):
        raise Phase1AResolverError("envelope must be an object")
    out = copy.deepcopy(envelope)

    task = ((out.get("payload") or {}).get("task") or {})
    if not isinstance(task, dict):
        raise Phase1AResolverError("payload.task must be an object")
    if "resolved" in task:
        raise Phase1AResolverError("untrusted_resolved_inbound")
    schema_version = task.get("schema_version")
    if schema_version != "clec.v1":
        try:
            schema_full_path = Path(schema_path).expanduser() if schema_path else DEFAULT_COMBINED_SCHEMA
            _validate_envelope(out, schema_full_path)
        except ValidationError as exc:
            raise Phase1AResolverError(f"schema_validation_failed: {exc.message}") from exc
    if schema_version == "clec.v1":
        _validate_clec_task(task)

    violations = find_hardpath_violations(out)
    if violations:
        first = violations[0]
        raise Phase1AResolverError(f"hard_path_detected:{first['path']}:{first['rule']}")

    resources: List[Dict[str, Any]] = []
    for ref in _extract_refs(task):
        try:
            resource = resolve_ref(ref, map_path=ref_map_path)
        except Exception as exc:
            raise Phase1AResolverError(f"ref_resolve_failed:{ref}:{exc}") from exc
        if resource.get("kind") != "path" or not str(resource.get("uri", "")).startswith("file://"):
            raise Phase1AResolverError(f"invalid_resolved_resource:{ref}")
        resources.append(resource)

    task["resolved"] = {"trust": True, "resources": resources, "resolved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    out["payload"]["task"] = task
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1A UI/Core/Executor intent resolver")
    parser.add_argument("--intent", required=True, help="intent to resolve (example: code.implement)")
    parser.add_argument("--payload", default="{}", help="optional payload JSON object")
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_ROUTING_FILE),
        help="routing contract YAML path",
    )
    args = parser.parse_args()

    try:
        payload = _parse_payload(args.payload)
        ok, result = resolve_intent(
            intent=args.intent,
            payload=payload,
            contract_path=_resolve_contract_path(args.contract),
        )
    except Phase1AResolverError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
