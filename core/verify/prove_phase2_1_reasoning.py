#!/usr/bin/env python3
"""Proof runner for Phase 2.1 governance reasoning DoD."""
from __future__ import annotations

import importlib
import os
import sys
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


def run_proof() -> bool:
    repo_root = Path(__file__).resolve().parents[2]
    old = _set_env(repo_root)
    try:
        pol = _load_policy_module()
        memory = pol.load_policy_memory()

        # Protected target: must escalate and block automation.
        protected_ctx = {
            "intent": "open dashboard",
            "url": "https://dash.cloudflare.com/login",
            "target": "https://dash.cloudflare.com/login",
            "status_code": 403,
            "headers": {"server": "cloudflare"},
            "task_text": "cf-challenge turnstile",
        }
        sense = pol.sense_target(protected_ctx)
        risk = pol.classify_risk(sense, memory)
        decision = pol.select_tool(protected_ctx, sense, risk, memory)
        pol.enforce_before_execute(decision, execution_tool="HEADLESS_AUTOMATION")

        # Reflect outcomes for >=3 protected domains.
        seed_domains = ["dash.cloudflare.com", "x.example", "y.example"]
        for domain in seed_domains:
            d = {
                **decision,
                "tool": "FIRECRAWL_SCRAPE",
                "risk_class": "Public-Unprotected",
                "sense": {"signals": [], "confidence": 0.8, "domain": domain},
                "human_required": False,
            }
            memory = pol.reflect_update_policy(
                d,
                {"status": 403, "headers": {"server": "cloudflare"}, "domain": domain, "evidence": "reflect-1"},
                memory,
            )
            memory = pol.reflect_update_policy(
                d,
                {"status": 429, "headers": {"server": "cloudflare"}, "domain": domain, "evidence": "reflect-2"},
                memory,
            )

        # Violation on confirmed protected domain.
        confirmed_decision = {
            **decision,
            "risk_class": "Protected",
            "sense": {**decision["sense"], "domain": "x.example"},
            "human_required": False,
        }
        pol.enforce_before_execute(confirmed_decision, execution_tool="FIRECRAWL_SCRAPE")

        return pol.emit_policy_verified_if_proven(actor="Auditor", phase="2.1")
    finally:
        _restore_env(old)


def main() -> int:
    ok = run_proof()
    print("phase2_1_reasoning_proof:", "ok" if ok else "failed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
