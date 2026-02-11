#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

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

from core.ref_resolver import resolve_ref
from core.verify.no_hardpath_guard import find_hardpath_violations

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "core/contracts/v1/0luka_schemas.json"
_REDACT_PATTERNS = [
    re.compile(r"file:///Users/[^\s\"']+"),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"C:\\Users\\[^\s\"']+"),
    re.compile(r"\\\\[^\\\s]+\\[^\\\s]+"),
]


class ResultGateError(RuntimeError):
    pass


def _load_combined_schema(path: Path) -> Dict[str, Any]:
    if validate is None:
        raise ResultGateError("missing dependency: jsonschema (pip install jsonschema)")
    if not path.exists():
        raise ResultGateError(f"schema_not_found:{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ResultGateError(f"invalid_schema_json:{exc}") from exc
    if not isinstance(data, dict):
        raise ResultGateError("invalid_schema_root")
    return data


def _validate_result_schema(result: Dict[str, Any]) -> None:
    schema = _load_combined_schema(SCHEMA_PATH)
    run_schema = {"$schema": schema.get("$schema"), "$ref": str(SCHEMA_PATH.resolve(strict=False).as_uri()) + "#/$defs/run_result"}
    try:
        if Draft202012Validator is None or Registry is None or Resource is None or DRAFT202012 is None:
            # TODO(phase2): migrate all jsonschema validation to a shared local-only Registry helper.
            validate(instance=result, schema=run_schema)
        else:
            resource = Resource(contents=schema, specification=DRAFT202012)
            registry = Registry().with_resource(SCHEMA_PATH.resolve(strict=False).as_uri(), resource)
            logical_id = schema.get("$id")
            if isinstance(logical_id, str) and logical_id:
                registry = registry.with_resource(logical_id, resource)
            Draft202012Validator(run_schema, registry=registry).validate(result)
    except ValidationError as exc:
        raise ResultGateError(f"schema_validation_failed:{exc.message}") from exc


def _build_uri_ref_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    refs = [
        "ref://repo/0luka",
        "ref://repo/core",
        "ref://interface/inbox",
        "ref://interface/outbox",
        "ref://artifacts",
        "ref://runtime",
    ]
    for ref in refs:
        try:
            resolved = resolve_ref(ref)
        except Exception:
            continue
        uri = str(resolved.get("uri", ""))
        if uri:
            mapping[uri] = ref
    return mapping


def _trusted_uris(result: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    resolved = result.get("resolved")
    if isinstance(resolved, dict) and resolved.get("trust") is True and isinstance(resolved.get("resources"), list):
        for row in resolved["resources"]:
            if isinstance(row, dict):
                uri = row.get("uri")
                if isinstance(uri, str) and uri:
                    out.append(uri)
    return out


def _sanitize_string(value: str, uri_to_ref: Dict[str, str], trusted_uris: List[str]) -> Tuple[str, bool]:
    out = value
    changed = False
    for uri in sorted(trusted_uris, key=len, reverse=True):
        ref = uri_to_ref.get(uri)
        if ref and uri in out:
            out = out.replace(uri, ref)
            changed = True
    for pat in _REDACT_PATTERNS:
        if pat.search(out):
            out = pat.sub("<redacted:path>", out)
            changed = True
    return out, changed


def _sanitize_obj(data: Any, uri_to_ref: Dict[str, str], trusted_uris: List[str], report: List[Dict[str, str]], path: str = "") -> Any:
    if isinstance(data, dict):
        out: Dict[str, Any] = {}
        for key, val in data.items():
            p = f"{path}/{key}" if path else f"/{key}"
            out[key] = _sanitize_obj(val, uri_to_ref, trusted_uris, report, p)
        return out
    if isinstance(data, list):
        out_list: List[Any] = []
        for idx, val in enumerate(data):
            p = f"{path}/{idx}" if path else f"/{idx}"
            out_list.append(_sanitize_obj(val, uri_to_ref, trusted_uris, report, p))
        return out_list
    if isinstance(data, str):
        sanitized, changed = _sanitize_string(data, uri_to_ref, trusted_uris)
        if changed:
            report.append({"path": path or "/", "action": "sanitize"})
        return sanitized
    return data


def _normalize_errors(result: Dict[str, Any]) -> None:
    if isinstance(result.get("error"), str):
        result["error"] = {"code": "ERR_RESULT_GATE", "summary": result["error"], "where": "result.error"}
    elif isinstance(result.get("error"), dict):
        e = result["error"]
        summary = e.get("summary") or e.get("message") or ""
        result["error"] = {
            "code": e.get("code") or "ERR_RESULT_GATE",
            "summary": summary,
            "where": e.get("where") or "result.error",
        }


def _enforce_evidence_minimum(result: Dict[str, Any]) -> None:
    if result.get("status") != "ok":
        return
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    commands = evidence.get("commands") if isinstance(evidence.get("commands"), list) else []
    effects = evidence.get("effects") if isinstance(evidence.get("effects"), list) else []
    if not commands and not effects:
        return
    logs = evidence.get("logs") if isinstance(evidence.get("logs"), list) else []
    outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
    artifacts = outputs.get("artifacts") if isinstance(outputs.get("artifacts"), list) else []
    provenance = result.get("provenance") if isinstance(result.get("provenance"), dict) else {}
    hashes = provenance.get("hashes") if isinstance(provenance.get("hashes"), dict) else {}
    hash_ok = bool(hashes.get("inputs_sha256")) and bool(hashes.get("outputs_sha256"))
    if not logs and not artifacts and not hash_ok:
        result["status"] = "error"
        result["reason"] = "missing_evidence_for_side_effect"


def gate_outbound_result(result: Dict[str, Any], *, mode: str = "normal") -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise ResultGateError("result must be an object")
    _validate_result_schema(result)

    out = copy.deepcopy(result)
    _normalize_errors(out)
    uri_to_ref = _build_uri_ref_map()
    trusted = _trusted_uris(out)
    redaction_report: List[Dict[str, str]] = []
    out = _sanitize_obj(out, uri_to_ref, trusted, redaction_report)
    if redaction_report:
        out["redaction_report"] = redaction_report

    _enforce_evidence_minimum(out)

    leaks = find_hardpath_violations(out)
    if leaks:
        raise ResultGateError(f"hard_path_leak:{leaks[0]['path']}:{leaks[0]['rule']}")
    return out
