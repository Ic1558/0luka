#!/usr/bin/env python3
"""
Tests for core/remediation_engine.py — Blueprint Pack 4E

Suites:
  1. test_policy_load_valid
  2. test_policy_load_invalid_action_rejected
  3. test_cooldown_suppression
  4. test_kill_pattern_dry_run
  5. test_evidence_written_on_execution
  6. test_circuit_breaker_trips_after_3_failures
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

import core.remediation_engine as engine
from core.remediation_engine import (
    COOLDOWN_STATE_PATH,
    RemediationError,
    _is_on_cooldown,
    _record_cooldown,
    _save_cooldown_state,
    evaluate_triggers,
    load_policy,
    run_remediation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy(triggers=None, allowed_actions=None, version=1) -> dict:
    if allowed_actions is None:
        allowed_actions = ["kill_process_group", "launchd_reload"]
    if triggers is None:
        triggers = [
            {
                "id": "test_ram_trigger",
                "condition": "ram_monitor.pressure_level == CRITICAL",
                "action": "kill_process_group",
                "params": {"patterns": ["TestHelper (Renderer)"], "signal": "SIGTERM", "max_targets": 1},
                "cooldown_sec": 10,
                "require_evidence": True,
            }
        ]
    return {"version": version, "allowed_actions": allowed_actions, "triggers": triggers}


def _write_policy_file(policy: dict, tmp_dir: Path) -> Path:
    p = tmp_dir / "remediation_policy.yaml"
    p.write_text(yaml.dump(policy), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Suite 1: test_policy_load_valid
# ---------------------------------------------------------------------------

def test_policy_load_valid():
    """Valid policy YAML loads without errors and contains expected triggers."""
    assert load_policy(engine.POLICY_PATH) is not None, "Policy load returned None"
    policy = load_policy(engine.POLICY_PATH)
    assert policy.get("version") == 1, f"Expected version=1, got {policy.get('version')}"
    assert isinstance(policy.get("triggers"), list), "triggers must be a list"
    assert len(policy["triggers"]) >= 1, "Expected at least 1 trigger"
    for t in policy["triggers"]:
        assert t.get("action") in engine.ALLOWED_ACTIONS, f"Unexpected action: {t.get('action')}"
    print("  PASS: policy_load_valid")


def test_policy_load_missing_file():
    """Missing policy file raises RemediationError."""
    try:
        load_policy(Path("/tmp/does_not_exist_remediation.yaml"))
        assert False, "Expected RemediationError"
    except RemediationError as exc:
        assert "policy_not_found" in str(exc)
    print("  PASS: policy_load_missing_file")


# ---------------------------------------------------------------------------
# Suite 2: test_policy_load_invalid_action_rejected
# ---------------------------------------------------------------------------

def test_policy_load_invalid_action_rejected():
    """Policy with unknown action is rejected at parse time (fail-closed)."""
    with tempfile.TemporaryDirectory() as td:
        bad_policy = _make_policy(
            allowed_actions=["rm_rf_root"],  # Not in ALLOWED_ACTIONS
            triggers=[{
                "id": "bad_trigger",
                "condition": "ram_monitor.pressure_level == CRITICAL",
                "action": "rm_rf_root",
                "params": {},
                "cooldown_sec": 60,
                "require_evidence": False,
            }]
        )
        p = _write_policy_file(bad_policy, Path(td))
        try:
            load_policy(p)
            assert False, "Expected RemediationError for unknown action"
        except RemediationError as exc:
            assert "unknown_actions" in str(exc), f"Wrong error: {exc}"
    print("  PASS: policy_load_invalid_action_rejected")


def test_policy_trigger_action_not_in_allowed_list():
    """Trigger referencing action not in allowed_actions list is rejected."""
    with tempfile.TemporaryDirectory() as td:
        bad_policy = {
            "version": 1,
            "allowed_actions": ["kill_process_group"],
            "triggers": [{
                "id": "sneaky_trigger",
                "condition": "ram_monitor.pressure_level == CRITICAL",
                "action": "launchd_reload",  # not in allowed_actions for this policy
                "params": {"service": "com.0luka.test"},
                "cooldown_sec": 60,
                "require_evidence": False,
            }]
        }
        p = _write_policy_file(bad_policy, Path(td))
        try:
            load_policy(p)
            assert False, "Expected RemediationError for action not in allowed_list"
        except RemediationError as exc:
            assert "action_not_in_allowed_list" in str(exc), f"Wrong error: {exc}"
    print("  PASS: policy_trigger_action_not_in_allowed_list")


# ---------------------------------------------------------------------------
# Suite 3: test_cooldown_suppression
# ---------------------------------------------------------------------------

def test_cooldown_suppression():
    """Trigger that just fired is suppressed (on cooldown)."""
    with tempfile.TemporaryDirectory() as td:
        state_path = Path(td) / "cooldown_state.json"
        # Simulate a recent fire
        state = {"test_ram_trigger": {"last_fire_epoch": time.time()}}
        state_path.write_text(json.dumps(state), encoding="utf-8")

        # Monkey-patch cooldown state path
        original = engine.COOLDOWN_STATE_PATH
        engine.COOLDOWN_STATE_PATH = state_path
        try:
            policy = _make_policy()
            policy_path = _write_policy_file(policy, Path(td))
            records = run_remediation(
                ram_state={"pressure_level": "CRITICAL"},
                dry_run=True,
                policy_path=policy_path,
            )
            assert len(records) == 1, f"Expected 1 record, got {len(records)}"
            assert records[0]["status"] == "suppressed_cooldown", f"Expected suppressed_cooldown: {records[0]}"
        finally:
            engine.COOLDOWN_STATE_PATH = original

    print("  PASS: cooldown_suppression")


def test_cooldown_not_suppressed_after_window():
    """Trigger fires normally when cooldown window has elapsed."""
    with tempfile.TemporaryDirectory() as td:
        state_path = Path(td) / "cooldown_state.json"
        # Simulate a fire that happened 2 hours ago (well past cooldown)
        state = {"test_ram_trigger": {"last_fire_epoch": time.time() - 7200}}
        state_path.write_text(json.dumps(state), encoding="utf-8")

        original_cooldown = engine.COOLDOWN_STATE_PATH
        original_evidence = engine.EVIDENCE_DIR
        original_log = engine.REMEDIATION_LOG
        engine.COOLDOWN_STATE_PATH = state_path
        engine.EVIDENCE_DIR = Path(td) / "evidence"
        engine.REMEDIATION_LOG = Path(td) / "remediation.jsonl"
        try:
            policy = _make_policy()
            policy_path = _write_policy_file(policy, Path(td))
            records = run_remediation(
                ram_state={"pressure_level": "CRITICAL"},
                dry_run=True,
                policy_path=policy_path,
            )
            assert len(records) == 1, f"Expected 1 record, got {len(records)}"
            assert records[0]["status"] != "suppressed_cooldown", f"Should NOT be suppressed: {records[0]}"
        finally:
            engine.COOLDOWN_STATE_PATH = original_cooldown
            engine.EVIDENCE_DIR = original_evidence
            engine.REMEDIATION_LOG = original_log

    print("  PASS: cooldown_not_suppressed_after_window")


# ---------------------------------------------------------------------------
# Suite 4: test_kill_pattern_dry_run
# ---------------------------------------------------------------------------

def test_kill_pattern_dry_run():
    """Dry-run kill_process_group returns dry_run status without killing anything."""
    from core.remediation_engine import _action_kill_process_group

    # Use a pattern that is almost certainly not running in this test environment
    params = {
        "patterns": ["DEFINITELY_NOT_RUNNING_xyz987"],
        "signal": "SIGTERM",
        "max_targets": 3,
    }
    result = _action_kill_process_group(params, dry_run=True)
    assert result.get("status") in ("dry_run", "ok"), f"Unexpected status: {result}"
    assert result.get("killed") == [], f"Should not kill in dry-run: {result}"
    print("  PASS: kill_pattern_dry_run")


def test_kill_pattern_returns_candidates():
    """kill_process_group identifies candidates from ps output."""
    from core.remediation_engine import _action_kill_process_group

    # Use a pattern that matches a known always-running process
    params = {
        "patterns": ["python3"],
        "signal": "SIGTERM",
        "max_targets": 1,
    }
    result = _action_kill_process_group(params, dry_run=True)
    # Should find at least one candidate (this test itself is python3)
    assert result.get("candidates_found", 0) >= 1, f"Expected >=1 candidates: {result}"
    assert result.get("status") == "dry_run", f"Expected dry_run status: {result}"
    print("  PASS: kill_pattern_returns_candidates")


# ---------------------------------------------------------------------------
# Suite 5: test_evidence_written_on_execution
# ---------------------------------------------------------------------------

def test_evidence_written_on_execution():
    """Evidence JSON is written when trigger fires (dry-run)."""
    with tempfile.TemporaryDirectory() as td:
        evidence_dir = Path(td) / "evidence"
        cooldown_path = Path(td) / "cooldown.json"
        log_path = Path(td) / "remediation.jsonl"

        original_ev = engine.EVIDENCE_DIR
        original_cs = engine.COOLDOWN_STATE_PATH
        original_log = engine.REMEDIATION_LOG
        engine.EVIDENCE_DIR = evidence_dir
        engine.COOLDOWN_STATE_PATH = cooldown_path
        engine.REMEDIATION_LOG = log_path

        try:
            policy = _make_policy()
            policy_path = _write_policy_file(policy, Path(td))
            records = run_remediation(
                ram_state={"pressure_level": "CRITICAL"},
                dry_run=True,
                policy_path=policy_path,
            )
            assert len(records) >= 1, f"Expected at least 1 record"
            r = records[0]
            # Evidence should be written even in dry-run (require_evidence=True)
            assert r.get("evidence") is not None, f"Evidence path should be set: {r}"
            ev_files = list(evidence_dir.iterdir())
            assert len(ev_files) >= 1, f"Expected evidence file in {evidence_dir}"
            ev_data = json.loads(ev_files[0].read_text(encoding="utf-8"))
            assert ev_data.get("trigger_id") == "test_ram_trigger"
        finally:
            engine.EVIDENCE_DIR = original_ev
            engine.COOLDOWN_STATE_PATH = original_cs
            engine.REMEDIATION_LOG = original_log

    print("  PASS: evidence_written_on_execution")


# ---------------------------------------------------------------------------
# Suite 6: test_circuit_breaker_trips_after_3_failures
# ---------------------------------------------------------------------------

def test_circuit_breaker_trips_after_3_failures():
    """CircuitBreaker trips (OPEN) after 3 consecutive failures in remediation engine."""
    from core.circuit_breaker import CircuitBreaker, CircuitOpenError

    cb = CircuitBreaker(name="test_remediation", failure_threshold=3, recovery_timeout_sec=999)

    def always_fail():
        raise RuntimeError("simulated_failure")

    # First 3 calls should fail normally
    failures = 0
    for _ in range(3):
        try:
            cb.call(always_fail)
        except RuntimeError:
            failures += 1

    assert failures == 3, f"Expected 3 failures, got {failures}"
    assert cb.state == CircuitBreaker.OPEN, f"Expected OPEN after 3 failures, got {cb.state}"

    # 4th call should raise CircuitOpenError
    try:
        cb.call(always_fail)
        assert False, "Expected CircuitOpenError"
    except CircuitOpenError:
        pass

    print("  PASS: circuit_breaker_trips_after_3_failures")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

SUITES = [
    # Suite 1
    test_policy_load_valid,
    test_policy_load_missing_file,
    # Suite 2
    test_policy_load_invalid_action_rejected,
    test_policy_trigger_action_not_in_allowed_list,
    # Suite 3
    test_cooldown_suppression,
    test_cooldown_not_suppressed_after_window,
    # Suite 4
    test_kill_pattern_dry_run,
    test_kill_pattern_returns_candidates,
    # Suite 5
    test_evidence_written_on_execution,
    # Suite 6
    test_circuit_breaker_trips_after_3_failures,
]


def main():
    passed = 0
    failed = 0
    for fn in SUITES:
        try:
            fn()
            passed += 1
        except Exception as exc:
            print(f"  FAIL: {fn.__name__}: {exc}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"remediation_engine: {passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
