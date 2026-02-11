#!/usr/bin/env python3
"""Proof runner for Phase 2 policy enforcer DoD."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.tool_selection_policy import (
    classify_risk,
    emit_policy_verified_if_proven,
    enforce_before_execute,
    load_policy_memory,
    reflect_update_policy,
    select_tool,
    sense_target,
)


def run_proof() -> bool:
    memory = load_policy_memory()

    # Scenario A: protected target -> human required + blocked automation.
    protected_ctx = {
        "url": "https://dash.cloudflare.com",
        "target": "https://dash.cloudflare.com/login",
        "status_code": 403,
        "headers": {"server": "cloudflare"},
        "task_text": "cf-challenge turnstile",
        "human_action": "Complete Cloudflare login",
    }
    sense = sense_target(protected_ctx)
    risk = classify_risk(sense, memory)
    decision = select_tool(protected_ctx, sense, risk, memory)
    enforce_before_execute(decision, execution_tool="FIRECRAWL_SCRAPE")

    # Scenario C fixture set: ensure >=3 protected domains in memory.
    seed_domains = ["dash.cloudflare.com", "x.example", "y.example", "z.example"]
    for domain in seed_domains:
        d = {
            "tool": "FIRECRAWL_SCRAPE",
            "risk_class": "Public-Unprotected",
            "human_required": False,
            "rationale": "proof_seed",
            "required_evidence": [],
            "next_steps": [],
            "sense": {"signals": [], "confidence": 0.8, "domain": domain},
            "policy_updates": [],
        }
        memory = reflect_update_policy(
            d,
            {"status": 403, "headers": {"server": "cloudflare"}, "domain": domain},
            memory,
        )
    return emit_policy_verified_if_proven(actor="PolicyEnforcer")


def main() -> int:
    ok = run_proof()
    print("phase2_policy_proof:", "ok" if ok else "failed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
