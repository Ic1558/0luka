#!/usr/bin/env python3
"""Phase 2 simulated tests for tool-selection policy."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "0LUKA_ROOT": os.environ.get("0LUKA_ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    os.environ["LUKA_RUNTIME_ROOT"] = str(root / "runtime")
    return old


def _restore_env(old: dict) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _load_policy_module():
    import importlib

    import core.config as cfg

    importlib.reload(cfg)
    mod = importlib.import_module("core.tool_selection_policy")
    return importlib.reload(mod)


def _read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_scenario_a_protected() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            pol = _load_policy_module()
            memory = pol.load_policy_memory()
            ctx = {
                "url": "https://dash.cloudflare.com",
                "target": "https://dash.cloudflare.com/login",
                "status_code": 403,
                "headers": {"server": "cloudflare"},
                "task_text": "cf-challenge turnstile",
                "human_action": "Complete Cloudflare login",
            }
            sense = pol.sense_target(ctx)
            risk = pol.classify_risk(sense, memory)
            decision = pol.select_tool(ctx, sense, risk, memory)
            assert decision["tool"] == "HUMAN_BROWSER"
            assert decision["risk_class"] == "Protected"
            blocked = pol.enforce_before_execute(decision, execution_tool="FIRECRAWL_SCRAPE")
            assert blocked["allowed"] is False
            events = _read_events(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "policy.human_escalation.requested" for e in events)
            print("test_scenario_a_protected: ok")
        finally:
            _restore_env(old)


def test_scenario_b_local() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            pol = _load_policy_module()
            memory = pol.load_policy_memory()
            ctx = {"target": "/" + "Users/icmini/0luka/.env.local"}
            sense = pol.sense_target(ctx)
            risk = pol.classify_risk(sense, memory)
            decision = pol.select_tool(ctx, sense, risk, memory)
            assert decision["risk_class"] == "Internal-Local"
            assert decision["tool"] in {"READ_FILE", "CLI"}
            kinds = {e["kind"] for e in decision["required_evidence"]}
            assert "file" in kinds
            assert "log" in kinds
            allowed = pol.enforce_before_execute(decision, execution_tool=decision["tool"])
            assert allowed["allowed"] is True
            print("test_scenario_b_local: ok")
        finally:
            _restore_env(old)


def test_scenario_c_reflect_update() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            pol = _load_policy_module()
            memory = pol.load_policy_memory()
            ctx = {
                "url": "https://x.example/login",
                "target": "https://x.example/login",
                "status_code": 403,
                "headers": {"server": "cloudflare"},
                "task_text": "cf-challenge",
            }
            sense = pol.sense_target(ctx)
            risk = pol.classify_risk(sense, memory)
            decision = pol.select_tool(ctx, sense, risk, memory)
            pol.enforce_before_execute(decision, execution_tool="HEADLESS_AUTOMATION")

            updated = pol.reflect_update_policy(
                decision,
                {"status": 403, "headers": {"server": "cloudflare"}, "domain": "x.example", "evidence": "e1"},
                memory,
            )
            updated = pol.reflect_update_policy(
                decision,
                {"status": 403, "headers": {"server": "cloudflare"}, "domain": "y.example", "evidence": "e2"},
                updated,
            )
            updated = pol.reflect_update_policy(
                decision,
                {"status": 403, "headers": {"server": "cloudflare"}, "domain": "z.example", "evidence": "e3"},
                updated,
            )
            domains = [row["domain"] for row in updated.get("protected_domains", [])]
            assert "x.example" in domains
            assert "y.example" in domains
            assert "z.example" in domains
            assert len(domains) >= 3
            assert pol.emit_policy_verified_if_proven(actor="PolicyEnforcer", phase="2.1") is True
            events = _read_events(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "policy.verified" for e in events)
            print("test_scenario_c_reflect_update: ok")
        finally:
            _restore_env(old)


def test_scenario_d_runtime_bootstrap_and_legacy_detection() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            legacy_path = root / "core" / "state" / "policy_memory.json"
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.write_text('{"legacy": true}\n', encoding="utf-8")

            pol = _load_policy_module()
            _ = pol.load_policy_memory()

            runtime_path = root / "runtime" / "state" / "policy_memory.json"
            assert runtime_path.exists()

            events = _read_events(root / "observability" / "events.jsonl")
            legacy_events = [e for e in events if e.get("type") == "policy.memory.legacy_detected"]
            assert legacy_events
            assert legacy_events[-1].get("legacy_path") == str(legacy_path)
            assert legacy_events[-1].get("runtime_path") == str(runtime_path)
            print("test_scenario_d_runtime_bootstrap_and_legacy_detection: ok")
        finally:
            _restore_env(old)


def test_scenario_e_legacy_path_reference_emits_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            pol = _load_policy_module()
            legacy_path = str(root / "core" / "state" / "policy_memory.json")
            pol.sense_target({"target": legacy_path, "task_text": "inspect legacy policy memory"})

            events = _read_events(root / "observability" / "events.jsonl")
            ref_events = [e for e in events if e.get("type") == "policy.memory.legacy_referenced"]
            assert ref_events
            assert ref_events[-1].get("legacy_path") == legacy_path
            print("test_scenario_e_legacy_path_reference_emits_event: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_scenario_a_protected()
    test_scenario_b_local()
    test_scenario_c_reflect_update()
    test_scenario_d_runtime_bootstrap_and_legacy_detection()
    test_scenario_e_legacy_path_reference_emits_event()
    print("test_tool_selection_policy: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
