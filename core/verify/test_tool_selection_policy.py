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
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
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
            ctx = {"target": "/Users/icmini/0luka/.env.local"}
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
            decision = {
                "tool": "FIRECRAWL_SCRAPE",
                "risk_class": "Public-Unprotected",
                "human_required": False,
                "rationale": "test",
                "required_evidence": [],
                "next_steps": [],
                "sense": {"signals": [], "confidence": 0.8, "domain": "x.example"},
                "policy_updates": [],
            }
            updated = pol.reflect_update_policy(
                decision,
                {"status": 403, "headers": {"server": "cloudflare"}, "domain": "x.example"},
                memory,
            )
            updated = pol.reflect_update_policy(
                decision,
                {"status": 403, "headers": {"server": "cloudflare"}, "domain": "y.example"},
                updated,
            )
            updated = pol.reflect_update_policy(
                decision,
                {"status": 403, "headers": {"server": "cloudflare"}, "domain": "z.example"},
                updated,
            )
            pol.append_event(
                {
                    "type": "policy.human_escalation.requested",
                    "category": "policy",
                    "risk_class": "Protected",
                    "domain": "x.example",
                }
            )
            domains = [row["domain"] for row in updated.get("protected_domains", [])]
            assert "x.example" in domains
            assert "y.example" in domains
            assert "z.example" in domains
            assert len(domains) >= 3
            assert pol.emit_policy_verified_if_proven(actor="PolicyEnforcer") is True
            events = _read_events(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "policy.verified" for e in events)
            print("test_scenario_c_reflect_update: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_scenario_a_protected()
    test_scenario_b_local()
    test_scenario_c_reflect_update()
    print("test_tool_selection_policy: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
