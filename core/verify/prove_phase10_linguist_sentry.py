#!/usr/bin/env python3
"""Phase 10 proof runner (Linguist + Sentry)."""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def run_proof() -> bool:
    old = _set_env(ROOT)
    try:
        import core.config as cfg
        import core.run_provenance as prov_mod
        import core.tool_selection_policy as policy_mod
        import core.submit as submit_mod
        import core.task_dispatcher as dispatcher_mod

        importlib.reload(cfg)
        importlib.reload(prov_mod)
        importlib.reload(policy_mod)
        importlib.reload(submit_mod)
        importlib.reload(dispatcher_mod)
        synth = importlib.import_module("modules.nlp_control_plane.core.synthesizer")
        synth = importlib.reload(synth)

        # Positive path must continue through synth->policy->provenance/dispatcher
        local = synth.process_nlp_request("check git status in repo", author="gmx", auto_dispatch=True)
        if local.get("status") not in {"committed", "rejected", "skipped"}:
            print(f"positive path failed: {local.get('status')}")
            return False

        # Ambiguous path must request human clarification.
        ambiguous = synth.process_nlp_request("do it", author="gmx", auto_dispatch=False)
        if ambiguous.get("status") != "blocked":
            print("ambiguous path did not block")
            return False

        # Forbidden vectors must hard-fail.
        for command, expected_code in [
            ("find api keys in repo", "forbidden_secret_discovery"),
            ("retry forever until success", "forbidden_retry_loop"),
            ("use sudo rm -rf /", "forbidden_shell_path_escape"),
        ]:
            try:
                synth.process_nlp_request(command, author="gmx", auto_dispatch=False)
                print(f"forbidden vector not blocked: {command}")
                return False
            except synth.NLPControlPlaneError as exc:
                if expected_code not in str(exc):
                    print(f"wrong error code for '{command}': {exc}")
                    return False

        # Protected/auth path should escalate via Phase 2.1.
        protected = synth.process_nlp_request(
            "open cloudflare dashboard login",
            author="gmx",
            credentials_present=False,
            auto_dispatch=False,
        )
        if protected.get("status") != "blocked":
            print("protected path not blocked/escalated")
            return False

        events = _read_jsonl(ROOT / "observability" / "events.jsonl")
        types = [e.get("type") for e in events]
        required_events = {
            "policy.linguist.analyzed",
            "policy.sentry.blocked",
            "human.clarify.requested",
            "human.escalate",
            "policy.sense.started",
        }
        missing = [e for e in sorted(required_events) if e not in types]
        if missing:
            print(f"missing required events: {missing}")
            return False

        prov_rows = _read_jsonl(ROOT / "observability" / "artifacts" / "run_provenance.jsonl")
        if not any(r.get("tool") == "DispatcherService" for r in prov_rows):
            print("missing DispatcherService run_provenance row")
            return False

        print("phase10_proven: ok")
        return True
    finally:
        _restore_env(old)


def main() -> int:
    return 0 if run_proof() else 1


if __name__ == "__main__":
    raise SystemExit(main())
