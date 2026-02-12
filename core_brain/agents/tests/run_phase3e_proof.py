#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_REL = Path("observability/reports/agents/phase_3e_cost_router_proof.json")
ACTIVITY_FEED_REL = Path("observability/logs/activity_feed.jsonl")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch_ms_now() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _load_modules():
    from core_brain.agents.cost_budget import check_budget, record_spend
    from core_brain.agents.cost_router import select_model

    return select_model, check_budget, record_spend


def _prepare_isolated_env() -> Dict[str, str]:
    sandbox = Path(tempfile.mkdtemp(prefix="phase3e_proof_"))
    registry_src = REPO_ROOT / "core_brain/agents/model_registry.yaml"
    registry_dst = sandbox / "model_registry.yaml"
    shutil.copy2(registry_src, registry_dst)
    decisions_path = sandbox / "decisions.jsonl"
    ledger_path = sandbox / "spend_ledger.jsonl"
    env = {
        "COST_ROUTER_MODEL_REGISTRY_PATH": str(registry_dst),
        "COST_ROUTER_DECISIONS_PATH": str(decisions_path),
        "COST_ROUTER_SPEND_LEDGER_PATH": str(ledger_path),
    }
    os.environ.update(env)
    return env


def _run_proof_cases(run_id: str) -> Dict[str, Any]:
    select_model, check_budget, record_spend = _load_modules()
    env = _prepare_isolated_env()
    decisions_path = Path(env["COST_ROUTER_DECISIONS_PATH"])
    ledger_path = Path(env["COST_ROUTER_SPEND_LEDGER_PATH"])
    registry_path = Path(env["COST_ROUTER_MODEL_REGISTRY_PATH"])
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    t2_cfg = registry.get("tiers", {}).get("T2", {})
    t2_limit = float(t2_cfg.get("daily_budget_limit", 0.0))

    cases = [
        ("risk_r3", {"task_id": "phase3e-risk-r3", "path": "core/config.py", "intent": "typo"}, "T0"),
        ("risk_r0", {"task_id": "phase3e-risk-r0", "path": "observability/logs/x.json", "intent": "typo"}, "T3"),
        ("complex_l3", {"task_id": "phase3e-l3", "path": "docs/note.md", "intent": "refactor pipeline architecture"}, "T0"),
        ("governance_override", {"task_id": "phase3e-gov", "intent": "modifies:core/governance/phase_status.yaml typo"}, "T0"),
        ("composition_floor", {"task_id": "phase3e-comp", "path": "modules/demo/a.py", "intent": "implement feature"}, "T1"),
    ]

    router_results: List[Dict[str, Any]] = []
    router_ok = True
    for name, task, expected_tier in cases:
        actual = select_model(task)
        got = str(actual.get("tier_selected"))
        ok = got == expected_tier
        router_ok = router_ok and ok
        router_results.append(
            {
                "case": name,
                "task": task,
                "expected_tier": expected_tier,
                "actual_tier": got,
                "ok": ok,
            }
        )

    deterministic_task = {"task_id": "phase3e-det", "path": "modules/demo/b.py", "intent": "fix bug"}
    deterministic = [select_model(deterministic_task).get("tier_selected") for _ in range(100)]
    deterministic_ok = len(set(deterministic)) == 1

    budget_allow = check_budget("T2")
    record_spend("T2", t2_limit)
    budget_daily_limit = check_budget("T2")

    bad_ledger = ledger_path.with_name("corrupted_spend_ledger.jsonl")
    bad_ledger.write_text("{not-json}\n", encoding="utf-8")
    os.environ["COST_ROUTER_SPEND_LEDGER_PATH"] = str(bad_ledger)
    budget_ledger_failure = check_budget("T2")
    os.environ["COST_ROUTER_SPEND_LEDGER_PATH"] = str(ledger_path)

    record_spend("T0", 5.0)
    record_spend("T0", 5.0)
    budget_t0_cap = check_budget("T0")

    decision_lines = 0
    if decisions_path.exists():
        decision_lines = len([ln for ln in decisions_path.read_text(encoding="utf-8").splitlines() if ln.strip()])
    ledger_lines = 0
    if ledger_path.exists():
        ledger_lines = len([ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()])

    summary_payload = {
        "run_id": run_id,
        "router": {
            "cases": router_results,
            "determinism": {
                "runs": 100,
                "unique_tiers": sorted(set(str(v) for v in deterministic)),
                "ok": deterministic_ok,
            },
            "decision_lines": decision_lines,
        },
        "budget": {
            "allow_within_limit": budget_allow,
            "deny_daily_limit": budget_daily_limit,
            "deny_ledger_failure": budget_ledger_failure,
            "deny_t0_daily_limit": budget_t0_cap,
            "ledger_lines": ledger_lines,
        },
    }
    checksum = hashlib.sha256(
        json.dumps(summary_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    summary_payload["payload_sha256"] = checksum
    summary_payload["ok"] = (
        router_ok
        and deterministic_ok
        and budget_allow.get("allowed") is True
        and budget_daily_limit == {"allowed": False, "reason": "daily_budget_exceeded"}
        and budget_ledger_failure == {"allowed": False, "reason": "ledger_read_failure"}
        and budget_t0_cap == {"allowed": False, "reason": "t0_daily_limit"}
        and decision_lines >= 1
        and ledger_lines >= 1
    )
    return summary_payload


def _append_activity_chain(run_id: str, evidence_rel: str) -> List[Dict[str, Any]]:
    feed_path = REPO_ROOT / ACTIVITY_FEED_REL
    base = _epoch_ms_now()
    events = [
        {"action": "started", "ts_epoch_ms": base, "ts_utc": _utc_now()},
        {"action": "completed", "ts_epoch_ms": base + 1, "ts_utc": _utc_now()},
        {"action": "verified", "ts_epoch_ms": base + 2, "ts_utc": _utc_now()},
    ]
    emitted: List[Dict[str, Any]] = []
    for raw in events:
        row = {
            "phase_id": "PHASE_3E",
            "action": raw["action"],
            "tool": "cost_router",
            "run_id": run_id,
            "emit_mode": "runtime_auto",
            "verifier_mode": "operational_proof",
            "ts_epoch_ms": raw["ts_epoch_ms"],
            "ts_utc": raw["ts_utc"],
            "evidence": [evidence_rel],
        }
        _append_jsonl(feed_path, row)
        emitted.append(row)
    return emitted


def main() -> int:
    parser = argparse.ArgumentParser(description="PHASE_3E operational proof harness")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    parser.add_argument("--no-activity", action="store_true", help="Skip activity feed emission")
    args = parser.parse_args()

    run_id = f"phase3e-{uuid.uuid4().hex}"
    ts_utc = _utc_now()
    evidence_abs = REPO_ROOT / EVIDENCE_REL
    evidence_rel = EVIDENCE_REL.as_posix()

    summary = _run_proof_cases(run_id)
    payload = {
        "phase_id": "PHASE_3E",
        "run_id": run_id,
        "ts_utc": ts_utc,
        "inputs": {
            "router_cases": [item["case"] for item in summary["router"]["cases"]],
            "budget_checks": [
                "allow_within_limit",
                "deny_daily_limit",
                "deny_ledger_failure",
                "deny_t0_daily_limit",
            ],
        },
        "expected_outputs": {
            "router_cases_ok": True,
            "determinism_ok": True,
            "budget_allow_within_limit": {"allowed": True},
            "budget_deny_daily_limit": {"allowed": False, "reason": "daily_budget_exceeded"},
            "budget_deny_ledger_failure": {"allowed": False, "reason": "ledger_read_failure"},
            "budget_deny_t0_daily_limit": {"allowed": False, "reason": "t0_daily_limit"},
        },
        "actual_outputs": summary,
        "ok": bool(summary.get("ok")),
    }
    _atomic_write_json(evidence_abs, payload)

    events = []
    if not args.no_activity:
        events = _append_activity_chain(run_id, evidence_rel)

    out = {
        "ok": payload["ok"],
        "phase_id": "PHASE_3E",
        "run_id": run_id,
        "evidence_path": evidence_rel,
        "events_emitted": len(events),
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(f"phase={out['phase_id']} run_id={run_id} ok={out['ok']} evidence={evidence_rel}")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
