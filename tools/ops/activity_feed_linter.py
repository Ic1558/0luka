#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import jsonschema

VALID_ACTIONS = {"started", "completed", "verified"}
REQUIRED_KEYS = (
    "ts_utc",
    "ts_epoch_ms",
    "phase_id",
    "action",
    "tool",
    "run_id",
    "emit_mode",
    "verifier_mode",
)
DEFAULT_SCHEMA_PATH = "core/observability/activity_feed.schema.json"


def _default_feed() -> Path:
    raw = os.environ.get("LUKA_ACTIVITY_FEED_JSONL", "observability/logs/activity_feed.jsonl").strip()
    return Path(raw)


def _runtime_error(message: str, as_json: bool) -> int:
    payload = {"ok": False, "error": message}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"activity_feed_linter_error:{message}", file=sys.stderr)
    return 4


def _validate(path: Path, strict: bool = False, schema_path: Path | None = None) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing_file:{path}")
    if not path.is_file():
        raise RuntimeError(f"not_a_file:{path}")
    if not os.access(path, os.R_OK):
        raise RuntimeError(f"unreadable_file:{path}")

    schema = None
    if schema_path and schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            schema = None

    total_lines = 0
    parsed_events = 0
    ignored_events = 0
    errors: List[Dict[str, Any]] = []
    
    # State for sequence validation
    last_ts_utc = ""
    grouped_chains: Dict[Tuple[str, str], List[Tuple[int, str, Any]]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            total_lines += 1
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid_json:line={line_no}:{exc}") from exc
            if not isinstance(payload, dict):
                raise RuntimeError(f"non_object_json:line={line_no}")
            parsed_events += 1

            # 1. Schema Validation (if enabled/available)
            if schema:
                try:
                    jsonschema.validate(instance=payload, schema=schema)
                except jsonschema.ValidationError as exc:
                    errors.append({
                        "line": line_no,
                        "action": payload.get("action"),
                        "error": "schema_violation",
                        "message": str(exc.message)
                    })
                    if strict: continue

            # 2. Timestamp Monotonicity
            ts_utc = payload.get("ts_utc")
            if ts_utc and isinstance(ts_utc, str):
                if last_ts_utc and ts_utc < last_ts_utc:
                    errors.append({
                        "line": line_no,
                        "error": "timestamp_regression",
                        "current": ts_utc,
                        "last": last_ts_utc
                    })
                last_ts_utc = ts_utc

            # 3. Operational Chain Validation (started/completed/verified)
            action = str(payload.get("action", "")).strip().lower()
            emit_mode = str(payload.get("emit_mode", "")).strip()
            verifier_mode = str(payload.get("verifier_mode", "")).strip()

            if action in VALID_ACTIONS and emit_mode == "runtime_auto" and verifier_mode == "operational_proof":
                phase_id = str(payload.get("phase_id", "unknown"))
                run_id = str(payload.get("run_id", "unknown"))
                grouped_chains.setdefault((phase_id, run_id), []).append((line_no, action, payload.get("status_badge")))
            else:
                ignored_events += 1

    # 4. Finalize Chain Validation
    for (phase_id, run_id), rows in grouped_chains.items():
        first: Dict[str, int] = {}
        completed_badge = None
        for line_no, action, status_badge in rows:
            if action not in first:
                first[action] = line_no
            if action == "completed" and completed_badge is None:
                completed_badge = status_badge
        
        started_ln = first.get("started")
        completed_ln = first.get("completed")
        verified_ln = first.get("verified")
        verify_required = (completed_badge != "NOT_PROVEN")
        
        if started_ln is None or completed_ln is None or (verify_required and verified_ln is None):
            errors.append({
                "phase_id": phase_id,
                "run_id": run_id,
                "error": "incomplete_chain",
                "has_started": started_ln is not None,
                "has_completed": completed_ln is not None,
                "has_verified": verified_ln is not None,
            })
            continue
            
        if verify_required:
            valid_order = started_ln < completed_ln < verified_ln
        else:
            valid_order = started_ln < completed_ln
            
        if not valid_order:
            errors.append({
                "phase_id": phase_id,
                "run_id": run_id,
                "error": "invalid_order",
                "started_line": started_ln,
                "completed_line": completed_ln,
                "verified_line": verified_ln,
            })

    violations = len(errors)
    return {
        "ok": violations == 0,
        "counts": {
            "total_lines": total_lines,
            "parsed_events": parsed_events,
            "ignored_events": ignored_events,
            "violations": violations,
        },
        "errors": errors[:100],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LUKA activity_feed.jsonl linter")
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    parser.add_argument("--path", help="Path to JSONL feed (overrides env)")
    parser.add_argument("--strict", action="store_true", help="Fail on any schema or sequence violation")
    parser.add_argument("--schema", help="Path to JSON schema file")
    args = parser.parse_args()

    feed = Path(args.path) if args.path else _default_feed()
    schema_path = Path(args.schema) if args.schema else Path(DEFAULT_SCHEMA_PATH)
    
    try:
        report = _validate(feed, strict=args.strict, schema_path=schema_path)
    except RuntimeError as exc:
        return _runtime_error(str(exc), args.json)
    except Exception as exc:
        return _runtime_error(f"internal_error:{type(exc).__name__}:{exc}", args.json)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"ok={report['ok']} violations={report['counts']['violations']} file={feed}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
