"""
trace_linter.py — Strict linter for activity feed and trace records.

Detects:
  - malformed JSONL lines (parse errors)
  - missing required trace fields
  - invalid or missing trace_version
  - broken snapshot linkage (warning only)

Safety:
  - read-only: no auto-repair, no mutation

Output contract (all functions):
  {
    "feed_path": str,
    "line_count": int,
    "valid_traces": int,
    "error_count": int,
    "warning_count": int,
    "violation_count": int,       # error_count + warning_count
    "violations": [
      {
        "line": int,
        "trace_id": str | None,
        "severity": "error" | "warning",
        "issue": str,
      }
    ],
    "summary": str,
  }
"""

import json
from pathlib import Path

from core.config import RUNTIME_LOGS_DIR
from core.snapshot_store import load_snapshot
from core.trace_versioning import is_supported

TRACE_FILE = RUNTIME_LOGS_DIR / "activity_feed.jsonl"

# Full Phase 4.1 trace contract — all fields always written by trace_writer.write_trace()
# Split by nullability:

# Must be present AND non-None
_REQUIRED_NONEMPTY = [
    "trace_id",
    "timestamp",
    "trace_version",
    "execution_mode",
    "normalized_task",
    "decision",
    "result",
]

# Must be present as keys — value may be None (trace_writer always writes these)
_REQUIRED_PRESENT = [
    "parent_trace_id",
    "command",
    "error",
]

# Combined — exported so callers can inspect full coverage
REQUIRED_FIELDS = _REQUIRED_NONEMPTY + _REQUIRED_PRESENT


def _lint_record(lineno: int, record: dict) -> list:
    """Return list of violation dicts for a single parsed record."""
    violations = []
    trace_id = record.get("trace_id")

    # fields that must be present AND non-None
    for field in _REQUIRED_NONEMPTY:
        if record.get(field) is None:
            violations.append({
                "line": lineno,
                "trace_id": trace_id,
                "severity": "error",
                "issue": f"missing required field: {field}",
            })

    # fields that must exist as keys (value may be None)
    for field in _REQUIRED_PRESENT:
        if field not in record:
            violations.append({
                "line": lineno,
                "trace_id": trace_id,
                "severity": "error",
                "issue": f"missing field key: {field}",
            })

    # trace_version type and value
    tv = record.get("trace_version")
    if tv is not None:
        if not isinstance(tv, str):
            violations.append({
                "line": lineno,
                "trace_id": trace_id,
                "severity": "error",
                "issue": f"trace_version must be str, got {type(tv).__name__}",
            })
        elif not is_supported(tv):
            violations.append({
                "line": lineno,
                "trace_id": trace_id,
                "severity": "error",
                "issue": f"unsupported trace_version: {tv!r}",
            })

    # snapshot linkage — warning only; missing snapshot = not replay-safe but not invalid
    if trace_id:
        try:
            snap = load_snapshot(trace_id)
            if snap is None:
                violations.append({
                    "line": lineno,
                    "trace_id": trace_id,
                    "severity": "warning",
                    "issue": "snapshot missing — trace not replay-safe",
                })
        except Exception as e:
            violations.append({
                "line": lineno,
                "trace_id": trace_id,
                "severity": "warning",
                "issue": f"snapshot check failed: {e}",
            })

    return violations


def _build_result(feed_path: str, line_count: int, all_violations: list,
                  valid_traces: int) -> dict:
    error_count = sum(1 for v in all_violations if v["severity"] == "error")
    warning_count = sum(1 for v in all_violations if v["severity"] == "warning")

    if not all_violations:
        summary = f"clean — {valid_traces}/{line_count} traces valid, 0 violations"
    else:
        summary = (
            f"{error_count} error(s), {warning_count} warning(s) "
            f"across {line_count} lines — {valid_traces} error-free traces"
        )

    return {
        "feed_path": feed_path,
        "line_count": line_count,
        "valid_traces": valid_traces,
        "error_count": error_count,
        "warning_count": warning_count,
        "violation_count": len(all_violations),
        "violations": all_violations,
        "summary": summary,
    }


def lint_feed(feed_path: str = None) -> dict:
    """
    Lint the activity feed (or a provided JSONL file path).

    Args:
        feed_path: Path to JSONL feed file. Defaults to the canonical feed.

    Returns:
        Structured lint report.
    """
    path = Path(feed_path) if feed_path else TRACE_FILE

    if not path.exists():
        return _build_result(str(path), 0, [], 0)

    line_count = 0
    valid_traces = 0
    all_violations = []

    with open(path, "r") as f:
        for lineno, raw_line in enumerate(f, 1):
            line_count += 1
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as e:
                all_violations.append({
                    "line": lineno,
                    "trace_id": None,
                    "severity": "error",
                    "issue": f"malformed JSONL: {e}",
                })
                continue

            record_violations = _lint_record(lineno, record)
            errors = [v for v in record_violations if v["severity"] == "error"]
            if not errors:
                valid_traces += 1
            all_violations.extend(record_violations)

    return _build_result(str(path), line_count, all_violations, valid_traces)


def lint_recent(limit: int = 20) -> dict:
    """
    Lint only the most recent N traces from the feed.
    Use this to check current-orchestrator traces separately from legacy records.

    Args:
        limit: Number of most-recent lines to lint (default 20).

    Returns:
        Structured lint report scoped to recent traces only.
    """
    if not TRACE_FILE.exists():
        return _build_result(str(TRACE_FILE), 0, [], 0)

    raw_lines = []
    with open(TRACE_FILE, "r") as f:
        for line in f:
            raw_lines.append(line)

    recent_lines = raw_lines[-limit:] if len(raw_lines) > limit else raw_lines

    line_count = 0
    valid_traces = 0
    all_violations = []

    for lineno_offset, raw_line in enumerate(recent_lines, 1):
        line_count += 1
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as e:
            all_violations.append({
                "line": lineno_offset,
                "trace_id": None,
                "severity": "error",
                "issue": f"malformed JSONL: {e}",
            })
            continue

        record_violations = _lint_record(lineno_offset, record)
        errors = [v for v in record_violations if v["severity"] == "error"]
        if not errors:
            valid_traces += 1
        all_violations.extend(record_violations)

    label = f"{str(TRACE_FILE)} [last {limit} lines]"
    return _build_result(label, line_count, all_violations, valid_traces)


def lint_records(records: list) -> dict:
    """
    Lint a list of raw record dicts directly (no file I/O).

    Args:
        records: List of trace dicts.

    Returns:
        Structured lint report.
    """
    line_count = len(records)
    valid_traces = 0
    all_violations = []

    for lineno, record in enumerate(records, 1):
        if not isinstance(record, dict):
            all_violations.append({
                "line": lineno,
                "trace_id": None,
                "severity": "error",
                "issue": f"record is not a dict: {type(record).__name__}",
            })
            continue

        record_violations = _lint_record(lineno, record)
        errors = [v for v in record_violations if v["severity"] == "error"]
        if not errors:
            valid_traces += 1
        all_violations.extend(record_violations)

    return _build_result("<in-memory>", line_count, all_violations, valid_traces)
