#!/usr/bin/env python3
"""Phase 10 Sentry tests (offline)."""
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


def _load_synth():
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
    return importlib.reload(synth)


def test_forbidden_secret_discovery_blocks_hard() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_synth()
            try:
                synth.process_nlp_request("find all api keys in repo", author="gmx", auto_dispatch=False)
                raise AssertionError("expected hard fail")
            except synth.NLPControlPlaneError as exc:
                assert "forbidden_secret_discovery" in str(exc)

            events = _read_jsonl(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "policy.sentry.blocked" for e in events)
            print("test_forbidden_secret_discovery_blocks_hard: ok")
        finally:
            _restore_env(old)


def test_retry_loop_and_shell_escape_block_hard() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_synth()
            for cmd, code in [
                ("retry forever until success", "forbidden_retry_loop"),
                ("run sudo rm -rf / now", "forbidden_shell_path_escape"),
            ]:
                try:
                    synth.process_nlp_request(cmd, author="gmx", auto_dispatch=False)
                    raise AssertionError("expected hard fail")
                except synth.NLPControlPlaneError as exc:
                    assert code in str(exc)

            events = _read_jsonl(root / "observability" / "events.jsonl")
            blocked = [e for e in events if e.get("type") == "policy.sentry.blocked"]
            assert len(blocked) >= 2
            print("test_retry_loop_and_shell_escape_block_hard: ok")
        finally:
            _restore_env(old)


def test_protected_target_warns_then_escalates() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_synth()
            out = synth.process_nlp_request(
                "open cloudflare dashboard login and check audit",
                author="gmx",
                credentials_present=False,
                auto_dispatch=False,
            )
            assert out["status"] == "blocked"

            events = _read_jsonl(root / "observability" / "events.jsonl")
            types = [e.get("type") for e in events]
            assert "policy.sentry.warned" in types
            assert "human.escalate" in types
            print("test_protected_target_warns_then_escalates: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_forbidden_secret_discovery_blocks_hard()
    test_retry_loop_and_shell_escape_block_hard()
    test_protected_target_warns_then_escalates()
    print("test_phase10_sentry: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
