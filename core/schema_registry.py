#!/usr/bin/env python3
"""
Schema Registry v1 - loads $defs from 0luka_schemas.json and validates payloads.

Usage:
    from core.schema_registry import validate
    validate("router_audit", payload)   # raises SchemaError on failure
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SCHEMA_PATH = Path(__file__).parent / "contracts/v1/0luka_schemas.json"
_cache: dict | None = None


class SchemaError(Exception):
    """Raised when payload fails schema validation."""


def _load_defs() -> dict:
    global _cache
    if _cache is None:
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            _cache = json.load(f).get("$defs", {})
    return _cache


def _check_type(value: Any, spec: dict) -> str | None:
    """Minimal type check. Returns error string or None."""
    expected = spec.get("type")
    if expected is None:
        return None
    type_map = {
        "string": str,
        "object": dict,
        "array": list,
        "boolean": bool,
        "integer": int,
        "number": (int, float),
    }
    py_type = type_map.get(expected)
    if py_type and not isinstance(value, py_type):
        return f"expected {expected}, got {type(value).__name__}"
    return None


def validate(schema_name: str, payload: dict) -> None:
    """Validate payload against a named $def schema.

    Checks:
      - required fields present
      - field types correct
      - const values match
      - enum values in allowed set
      - additionalProperties: false enforced

    Raises SchemaError on first violation.
    """
    defs = _load_defs()
    if schema_name not in defs:
        raise SchemaError(f"unknown_schema:{schema_name}")

    schema = defs[schema_name]
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    missing = required - set(payload.keys())
    if missing:
        raise SchemaError(f"missing_required:{','.join(sorted(missing))}")

    if schema.get("additionalProperties") is False:
        extra = set(payload.keys()) - set(props.keys())
        if extra:
            raise SchemaError(f"extra_fields:{','.join(sorted(extra))}")

    for key, val in payload.items():
        if key not in props:
            continue
        field_spec = props[key]

        err = _check_type(val, field_spec)
        if err:
            raise SchemaError(f"field:{key}:{err}")

        if "const" in field_spec and val != field_spec["const"]:
            raise SchemaError(f"field:{key}:must_be:{field_spec['const']}")

        if "enum" in field_spec and val not in field_spec["enum"]:
            raise SchemaError(
                f"field:{key}:invalid_value:{val}:allowed:{field_spec['enum']}"
            )

        if "minLength" in field_spec and isinstance(val, str):
            if len(val) < field_spec["minLength"]:
                raise SchemaError(f"field:{key}:too_short")
