#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

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


def _validate(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing_file:{path}")
    if not path.is_file():
        raise RuntimeError(f"not_a_file:{path}")
    if not os.access(path, os.R_OK):
        raise RuntimeError(f"unreadable_file:{path}")

    total_lines = 0
    parsed_events = 0
    proof_events = 0
    ignored_events = 0
    missing_hist: Dict[str, int] = {}
    chain_errors: List[Dict[str, Any]] = []
    grouped: Dict[Tuple[str, str], List[Tuple[int, str]]] = {}

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

            action = str(payload.get("action", "")).strip().lower()
            if action not in VALID_ACTIONS:
                ignored_events += 1
                continue

            emit_mode = str(payload.get("emit_mode", "")).strip()
            verifier_mode = str(payload.get("verifier_mode", "")).strip()
            # Ignore non-operational/legacy records; this linter validates
            # operational-proof chains only.
            if emit_mode != "runtime_auto" or verifier_mode != "operational_proof":
                ignored_events += 1
                continue

            proof_events += 1
            missing = [k for k in REQUIRED_KEYS if k not in payload]
            if missing:
                for key in missing:
                    missing_hist[key] = missing_hist.get(key, 0) + 1
                chain_errors.append(
                    {
                        "line": line_no,
                        "phase_id": payload.get("phase_id"),
                        "run_id": payload.get("run_id"),
                        "error": "missing_required_keys",
                        "missing_keys": missing,
                    }
                )
                continue

            phase_id = str(payload.get("phase_id"))
            run_id = str(payload.get("run_id"))
            grouped.setdefault((phase_id, run_id), []).append((line_no, action))

    for (phase_id, run_id), rows in grouped.items():
        first: Dict[str, int] = {}
        for line_no, action in rows:
            if action not in first:
                first[action] = line_no
        started_ln = first.get("started")
        completed_ln = first.get("completed")
        verified_ln = first.get("verified")
        if started_ln is None or completed_ln is None or verified_ln is None:
            chain_errors.append(
                {
                    "phase_id": phase_id,
                    "run_id": run_id,
                    "error": "incomplete_chain",
                    "has_started": started_ln is not None,
                    "has_completed": completed_ln is not None,
                    "has_verified": verified_ln is not None,
                }
            )
            continue
        if not (started_ln < completed_ln < verified_ln):
            chain_errors.append(
                {
                    "phase_id": phase_id,
                    "run_id": run_id,
                    "error": "invalid_order",
                    "started_line": started_ln,
                    "completed_line": completed_ln,
                    "verified_line": verified_ln,
                }
            )

    violations = len(chain_errors) + sum(missing_hist.values())
    ok = violations == 0
    return {
        "ok": ok,
        "counts": {
            "total_lines": total_lines,
            "parsed_events": parsed_events,
            "proof_events": proof_events,
            "ignored_events": ignored_events,
            "violations": violations,
        },
        "missing_fields": missing_hist,
        "chain_errors": chain_errors[:100],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LUKA activity_feed.jsonl linter")
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    parser.add_argument("--path", help="Path to JSONL feed (overrides env)")
    args = parser.parse_args()

    feed = Path(args.path) if args.path else _default_feed()
    try:
        report = _validate(feed)
    except RuntimeError as exc:
        return _runtime_error(str(exc), args.json)
    except Exception as exc:  # defensive fail-closed
        return _runtime_error(f"internal_error:{type(exc).__name__}:{exc}", args.json)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"ok={report['ok']} violations={report['counts']['violations']} file={feed}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
