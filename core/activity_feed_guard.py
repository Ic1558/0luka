from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    from core.config import ROOT, RUNTIME_ROOT, ACTIVITY_FEED_PATH, VIOLATION_LOG_PATH
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import ROOT, RUNTIME_ROOT, ACTIVITY_FEED_PATH, VIOLATION_LOG_PATH

STATE_PATH = RUNTIME_ROOT / "activity_feed_state.json"
CANONICAL_PRODUCTION_FEED_PATH = ACTIVITY_FEED_PATH.resolve()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_last_nonempty_line(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return ""
    with path.open("rb") as handle:
        pos = handle.seek(0, os.SEEK_END)
        buf = b""
        while pos > 0:
            step = 4096 if pos >= 4096 else pos
            pos -= step
            handle.seek(pos, os.SEEK_SET)
            buf = handle.read(step) + buf
            for raw in reversed(buf.splitlines()):
                if raw.strip():
                    return raw.decode("utf-8", errors="replace")
    return ""


def _write_state_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _append_violation(reason: str, detail: dict[str, Any], violation_log_path: Path) -> None:
    violation_log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts_utc": _utc_now(),
        "ts": _utc_now(),
        "phase_id": "B2_FEED_IMMUTABILITY",
        "action": "feed_guard_violation",
        "status_badge": "NOT_PROVEN",
        "reason": reason,
        "detail": detail,
    }
    with violation_log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def guarded_append_activity_feed(
    feed_path: Path,
    payload: dict[str, Any],
    *,
    state_path: Path = STATE_PATH,
    violation_log_path: Path = VIOLATION_LOG_PATH,
) -> bool:
    incoming = Path(feed_path).resolve()
    old_repo_path = (ROOT / "observability/logs/activity_feed.jsonl").resolve()
    emit_redirect_telemetry = False
    redirect_source_path = ""

    # Migration Redirect: If caller uses the legacy repo path, force it to the canonical runtime path.
    if incoming == old_repo_path and incoming != CANONICAL_PRODUCTION_FEED_PATH:
        # Prevent recursive redirect loops for telemetry events.
        if payload.get("action") != "legacy_feed_path_redirected":
            emit_redirect_telemetry = True
            redirect_source_path = str(incoming)
        incoming = CANONICAL_PRODUCTION_FEED_PATH

    if incoming != CANONICAL_PRODUCTION_FEED_PATH:
        incoming.parent.mkdir(parents=True, exist_ok=True)
        with incoming.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True

    feed_path = incoming
    state = _load_state(state_path)
    last_size = int(state.get("last_size_bytes") or 0)
    last_hash = str(state.get("last_line_hash") or "")
    current_size = feed_path.stat().st_size if feed_path.exists() else 0

    if current_size < last_size:
        _append_violation(
            "truncate_detected",
            {
                "feed_path": str(feed_path),
                "expected_min_size_bytes": last_size,
                "observed_size_bytes": current_size,
            },
            violation_log_path,
        )
        return False

    current_last = _read_last_nonempty_line(feed_path)
    current_hash = _sha256_text(current_last) if current_last else ""
    if last_hash and current_hash != last_hash:
        _append_violation(
            "rewrite_detected",
            {
                "feed_path": str(feed_path),
                "expected_last_line_hash": last_hash,
                "observed_last_line_hash": current_hash,
            },
            violation_log_path,
        )
        return False

    feed_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if emit_redirect_telemetry:
        telemetry_event = {
            "ts_utc": _utc_now(),
            "action": "legacy_feed_path_redirected",
            "emit_mode": "runtime_auto",
            "verifier_mode": "guard_intercept",
            "detail": {"original_path": redirect_source_path},
        }
        lines.append(json.dumps(telemetry_event, ensure_ascii=False))
    line = json.dumps(payload, ensure_ascii=False)
    lines.append(line)
    with feed_path.open("a", encoding="utf-8") as handle:
        for item in lines:
            handle.write(item + "\n")

    _write_state_atomic(
        state_path,
        {
            "feed_path": str(feed_path),
            "last_size_bytes": feed_path.stat().st_size,
            "last_line_hash": _sha256_text(line),
            "last_ts_utc": _utc_now(),
        },
    )
    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Guarded Activity Feed Append CLI")
    parser.add_argument("payload", help="JSON payload to append")
    parser.add_argument("--feed", help="Optional path override")

    args = parser.parse_args()

    try:
        from core.config import ACTIVITY_FEED_PATH
    except ImportError:
        ACTIVITY_FEED_PATH = Path("observability/logs/activity_feed.jsonl")

    feed = Path(args.feed) if args.feed else ACTIVITY_FEED_PATH
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON payload: {exc}", file=sys.stderr)
        sys.exit(1)

    if guarded_append_activity_feed(feed, payload):
        sys.exit(0)
    else:
        print("Error: Guard blocked append (check violations log)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
