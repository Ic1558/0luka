#!/usr/bin/env python3
"""Phase 2.1 reasoning + governance tests (offline, simulated)."""
from __future__ import annotations

import importlib
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
    import core.config as cfg
    import core.reasoning_audit as ra

    importlib.reload(cfg)
    importlib.reload(ra)
    mod = importlib.import_module("core.tool_selection_policy")
    return importlib.reload(mod)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_protected_escalates_and_blocks_headless() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            pol = _load_policy_module()
            memory = pol.load_policy_memory()
            ctx = {
                "intent": "open dashboard",
                "url": "https://dash.cloudflare.com/login",
                "target": "https://dash.cloudflare.com/login",
                "status_code": 403,
                "headers": {"server": "cloudflare"},
                "task_text": "cf-challenge turnstile",
            }
            sense = pol.sense_target(ctx)
            risk = pol.classify_risk(sense, memory)
            decision = pol.select_tool(ctx, sense, risk, memory)

            assert decision["risk_class"] == "Protected"
            assert decision["human_required"] is True
            assert decision["djm"]["human_justification"]

            blocked = pol.enforce_before_execute(decision, execution_tool="HEADLESS_AUTOMATION")
            assert blocked["allowed"] is False

            events = _read_jsonl(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "human.escalate" for e in events)
            assert any(e.get("type") == "policy.violation" for e in events)

            reasoning = _read_jsonl(root / "observability" / "audit" / "reasoning.jsonl")
            assert len(reasoning) >= 1
            assert "djm" in reasoning[-1]
            print("test_protected_escalates_and_blocks_headless: ok")
        finally:
            _restore_env(old)


def test_internal_local_read_file_path() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            pol = _load_policy_module()
            memory = pol.load_policy_memory()
            ctx = {"target": "/" + "Users/icmini/0luka/.env.local", "intent": "inspect env"}
            sense = pol.sense_target(ctx)
            risk = pol.classify_risk(sense, memory)
            decision = pol.select_tool(ctx, sense, risk, memory)

            assert decision["risk_class"] == "Internal-Local"
            assert decision["tool"] in {"READ_FILE", "CLI"}
            kinds = {row["kind"] for row in decision["required_evidence"]}
            assert "file" in kinds
            assert "log" in kinds

            allowed = pol.enforce_before_execute(decision)
            assert allowed["allowed"] is True
            print("test_internal_local_read_file_path: ok")
        finally:
            _restore_env(old)


def test_reflect_promotes_to_confirmed_and_freezes() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            pol = _load_policy_module()
            memory = pol.load_policy_memory()
            ctx = {
                "url": "https://x.example/login",
                "target": "https://x.example/login",
                "status_code": 200,
                "headers": {},
                "intent": "fetch",
            }
            sense = pol.sense_target(ctx)
            risk = pol.classify_risk(sense, memory)
            decision = pol.select_tool(ctx, sense, risk, memory)

            memory = pol.reflect_update_policy(
                decision,
                {"status": 403, "headers": {"server": "cloudflare"}, "domain": "x.example", "evidence": "h1"},
                memory,
            )
            memory = pol.reflect_update_policy(
                decision,
                {"status": 429, "headers": {"server": "cloudflare"}, "domain": "x.example", "evidence": "h2"},
                memory,
            )

            rows = memory.get("protected_domains", [])
            row = next((r for r in rows if r.get("domain") == "x.example"), None)
            assert row is not None
            assert row.get("state") == "CONFIRMED"
            assert row.get("frozen") is True

            blocked = pol.enforce_before_execute(
                {
                    **decision,
                    "risk_class": "Protected",
                    "sense": {**decision["sense"], "domain": "x.example"},
                    "human_required": False,
                },
                execution_tool="FIRECRAWL_SCRAPE",
            )
            assert blocked["allowed"] is False
            events = _read_jsonl(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "policy.violation" for e in events)
            print("test_reflect_promotes_to_confirmed_and_freezes: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_protected_escalates_and_blocks_headless()
    test_internal_local_read_file_path()
    test_reflect_promotes_to_confirmed_and_freezes()
    print("test_phase2_1_reasoning: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
