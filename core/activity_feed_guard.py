from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

try:
    from core.config import RUNTIME_ROOT
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import RUNTIME_ROOT

STATE_PATH = RUNTIME_ROOT / "state" / "activity_feed_state.json"
VIOLATION_LOG_PATH = RUNTIME_ROOT / "logs" / "feed_guard_violations.jsonl"
CANONICAL_PRODUCTION_FEED_PATH = (RUNTIME_ROOT / "logs" / "activity_feed.jsonl").resolve()
ANCHOR_ACTION = "ledger_anchor"
GENESIS_PREV_HASH = "GENESIS"
TAIL_SCAN_BYTES = 262_144


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_hash_payload(event_obj: dict[str, Any], prev_hash: str) -> tuple[dict[str, Any], str]:
    payload = dict(event_obj)
    payload.pop("hash", None)
    payload["prev_hash"] = prev_hash
    canonical_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    line_obj = dict(payload)
    line_obj["hash"] = digest
    return line_obj, digest


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


def _decode_json_line(raw: bytes) -> dict[str, Any] | None:
    try:
        decoded = raw.decode("utf-8")
    except Exception:
        decoded = raw.decode("utf-8", errors="replace")
    line = decoded.strip()
    if not line:
        return None
    try:
        parsed = json.loads(line)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_last_hashed_entry_locked(handle: Any, *, tail_scan_bytes: int = TAIL_SCAN_BYTES) -> dict[str, Any] | None:
    handle.seek(0, os.SEEK_END)
    file_size = handle.tell()
    if file_size <= 0:
        return None

    read_size = min(file_size, tail_scan_bytes)
    start = file_size - read_size
    handle.seek(start, os.SEEK_SET)
    block = handle.read(read_size)
    if isinstance(block, str):
        block = block.encode("utf-8")

    if start > 0:
        nl = block.find(b"\n")
        if nl >= 0:
            block = block[nl + 1 :]
        else:
            block = b""

    lines = block.splitlines()
    for raw in reversed(lines):
        parsed = _decode_json_line(raw)
        if not parsed:
            continue
        line_hash = parsed.get("hash")
        if isinstance(line_hash, str) and line_hash.strip():
            return parsed

    if start == 0:
        return None

    handle.seek(0, os.SEEK_SET)
    found: dict[str, Any] | None = None
    for raw in handle:
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        parsed = _decode_json_line(raw)
        if not parsed:
            continue
        line_hash = parsed.get("hash")
        if isinstance(line_hash, str) and line_hash.strip():
            found = parsed
    return found


def _append_json_line_locked(handle: Any, entry: dict[str, Any]) -> None:
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    handle.seek(0, os.SEEK_END)
    handle.write(line.encode("utf-8"))
    handle.flush()
    os.fsync(handle.fileno())


@contextlib.contextmanager
def _locked_feed(feed_path: Path):
    if fcntl is None:
        raise RuntimeError("flock_unavailable")
    feed_path.parent.mkdir(parents=True, exist_ok=True)
    with feed_path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            raise RuntimeError(f"flock_lock_failed:{exc}") from exc
        try:
            yield handle
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


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


def _ensure_anchor_atomic(feed_path: Path, state_path: Path) -> bool:
    with _locked_feed(feed_path) as handle:
        last_hashed = _read_last_hashed_entry_locked(handle)
        if last_hashed is not None:
            return True

        anchor_payload = {
            "ts_utc": _utc_now(),
            "ts_epoch_ms": int(time.time_ns() // 1_000_000),
            "phase_id": "LEDGER_PHASE2_DARK_LAUNCH",
            "action": ANCHOR_ACTION,
            "emit_mode": "runtime_auto",
            "verifier_mode": "operational_proof",
            "tool": "activity_feed_guard",
            "run_id": f"anchor_{uuid.uuid4().hex}",
        }
        anchor_entry, anchor_hash = _canonical_hash_payload(anchor_payload, GENESIS_PREV_HASH)
        _append_json_line_locked(handle, anchor_entry)
        handle.seek(0, os.SEEK_END)
        _write_state_atomic(
            state_path,
            {
                "feed_path": str(feed_path),
                "last_size_bytes": handle.tell(),
                "last_line_hash": _sha256_text(json.dumps(anchor_entry, ensure_ascii=False)),
                "last_event_hash": anchor_hash,
                "last_ts_utc": _utc_now(),
            },
        )
        return True


def guarded_append_activity_feed(
    feed_path: Path,
    payload: dict[str, Any],
    *,
    state_path: Path = STATE_PATH,
    violation_log_path: Path = VIOLATION_LOG_PATH,
) -> bool:
    feed_path = CANONICAL_PRODUCTION_FEED_PATH
    if not isinstance(payload, dict):
        _append_violation(
            "invalid_payload_type",
            {"feed_path": str(feed_path), "observed_type": str(type(payload).__name__)},
            violation_log_path,
        )
        return False

    try:
        _ensure_anchor_atomic(feed_path, state_path)
    except Exception as exc:
        _append_violation(
            "anchor_append_failed",
            {"feed_path": str(feed_path), "error": str(exc)},
            violation_log_path,
        )
        return False

    try:
        with _locked_feed(feed_path) as handle:
            state = _load_state(state_path)
            last_size = int(state.get("last_size_bytes") or 0)
            last_hash = str(state.get("last_line_hash") or "")
            handle.seek(0, os.SEEK_END)
            current_size = handle.tell()

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

            last_hashed = _read_last_hashed_entry_locked(handle)
            if last_hashed is None:
                _append_violation(
                    "missing_anchor",
                    {"feed_path": str(feed_path), "reason": "no_hashed_entry_found_after_anchor_phase"},
                    violation_log_path,
                )
                return False

            prev_hash = str(last_hashed.get("hash") or "")
            if not prev_hash:
                _append_violation(
                    "invalid_prev_hash_source",
                    {"feed_path": str(feed_path)},
                    violation_log_path,
                )
                return False

            chained_entry, entry_hash = _canonical_hash_payload(payload, prev_hash)
            _append_json_line_locked(handle, chained_entry)
            handle.seek(0, os.SEEK_END)
            new_size = handle.tell()

            _write_state_atomic(
                state_path,
                {
                    "feed_path": str(feed_path),
                    "last_size_bytes": new_size,
                    "last_line_hash": _sha256_text(json.dumps(chained_entry, ensure_ascii=False)),
                    "last_event_hash": entry_hash,
                    "last_ts_utc": _utc_now(),
                },
            )
        return True
    except Exception as exc:
        _append_violation(
            "append_failed",
            {"feed_path": str(feed_path), "error": str(exc)},
            violation_log_path,
        )
        return False
