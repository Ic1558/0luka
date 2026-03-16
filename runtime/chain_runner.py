"""AG-58: Mission Control Chain Runner.

Runs ordered chains of steps from CHAIN_REGISTRY. Each step returns a
result dict with status (PASS/FAIL) and summary. Chain stops on first FAIL.

Artifacts (under LUKA_RUNTIME_ROOT/state/):
  runtime_chain_runner_latest.json   — last chain report
  runtime_chain_runner_log.jsonl     — append-only history
  runtime_chain_runner_index.json    — slim index of all runs
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from runtime.chain_runner_policy import CHAIN_REGISTRY


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _append_log(path: Path, record: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _update_index(path: Path, entry: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (json.JSONDecodeError, OSError):
        existing = []
    if not isinstance(existing, list):
        existing = []
    existing.append(entry)
    _atomic_write(path, existing)


def run_chain(chain_name: str, operator_id: str) -> dict[str, Any]:
    """Run a named chain, collect per-step results, stop on FAIL, persist report."""
    if chain_name not in CHAIN_REGISTRY:
        raise ValueError(f"Unknown chain: {chain_name!r}. Available: {list(CHAIN_REGISTRY.keys())}")

    chain_id = uuid.uuid4().hex
    ts_started = _now()
    steps_config = CHAIN_REGISTRY[chain_name]

    step_results: list[dict[str, Any]] = []
    overall_status = "PASS"
    stop_reason: str | None = None

    for step_name, step_factory in steps_config:
        fn = step_factory()
        try:
            result = fn()
        except Exception as exc:
            result = {"status": "FAIL", "summary": f"exception: {exc}", "artifacts": []}

        step_record = {
            "step_name": step_name,
            "status": result.get("status", "FAIL"),
            "summary": result.get("summary", ""),
            "artifacts": result.get("artifacts", []),
        }
        step_results.append(step_record)

        if result.get("status") != "PASS":
            overall_status = "FAIL"
            stop_reason = f"step {step_name!r} returned {result.get('status', 'FAIL')}: {result.get('summary', '')}"
            break

    ts_finished = _now()

    # PARTIAL if some steps passed before a FAIL (but if all failed from first step, still FAIL)
    if overall_status == "FAIL" and len(step_results) > 1:
        passed = sum(1 for s in step_results if s["status"] == "PASS")
        if passed > 0:
            overall_status = "PARTIAL"

    report: dict[str, Any] = {
        "chain_id": chain_id,
        "chain_name": chain_name,
        "operator_id": operator_id,
        "steps": step_results,
        "overall_status": overall_status,
        "ts_started": ts_started,
        "ts_finished": ts_finished,
        "stop_reason": stop_reason,
    }

    state = _state_dir()
    _atomic_write(state / "runtime_chain_runner_latest.json", report)
    _append_log(state / "runtime_chain_runner_log.jsonl", report)
    _update_index(state / "runtime_chain_runner_index.json", {
        "chain_id": chain_id,
        "chain_name": chain_name,
        "overall_status": overall_status,
        "ts_started": ts_started,
        "ts_finished": ts_finished,
    })

    return report


def get_chain(chain_id: str) -> dict[str, Any] | None:
    """Read a chain report by chain_id from the log."""
    log_path = _state_dir() / "runtime_chain_runner_log.jsonl"
    if not log_path.exists():
        return None
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if record.get("chain_id") == chain_id:
                return record
        except json.JSONDecodeError:
            pass
    return None


def list_chains() -> list[dict[str, Any]]:
    """Read the chain run index."""
    index_path = _state_dir() / "runtime_chain_runner_index.json"
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
