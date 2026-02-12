#!/usr/bin/env python3
"""Phase 11 unit tests: sanitization, leak protection, injection neutralization, observer-only guard."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "phase11_audit_signal_snapshot.json"


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


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_narrator():
    import core.config as cfg

    importlib.reload(cfg)
    mod = importlib.import_module("modules.activity_intelligence.core.narrator")
    return importlib.reload(mod)


def test_sanitization_and_no_leak() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            events = root / "observability" / "events.jsonl"
            _append_jsonl(
                events,
                {
                    "ts": "2026-02-10T00:00:00Z",
                    "type": "policy.sense.started",
                    "message": "reading " + "/" + "Users/icmini/private/secret.txt with sk-ABCDEF1234567890123456",
                },
            )

            narrator = _load_narrator()
            out = narrator.generate_activity_intelligence(limit=20, write_artifacts=True)
            serialized = json.dumps(out, ensure_ascii=False)
            assert "/" + "Users/" not in serialized
            assert "sk-" not in serialized
            print("test_sanitization_and_no_leak: ok")
        finally:
            _restore_env(old)


def test_injection_vector_neutralized_and_block_signal() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            events = root / "observability" / "events.jsonl"
            _append_jsonl(
                events,
                {
                    "ts": "2026-02-10T00:00:00Z",
                    "type": "policy.sentry.blocked",
                    "message": "; rm -rf /",
                    "intent": "run ; rm -rf /",
                },
            )

            narrator = _load_narrator()
            out = narrator.generate_activity_intelligence(limit=20, write_artifacts=False)
            assert out["audit_signals"], "expected at least one audit signal"
            sig = out["audit_signals"][0]
            assert sig["schema_version"] == "audit.signal.v1"
            assert sig["signal_type"] == "RISK_SPIKE"
            assert "rm -rf" not in json.dumps(sig, ensure_ascii=False)

            expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
            for key, value in expected.items():
                assert sig[key] == value
            print("test_injection_vector_neutralized_and_block_signal: ok")
        finally:
            _restore_env(old)


def test_observer_only_static_guard() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            narrator = _load_narrator()
            narrator.static_guard()
            print("test_observer_only_static_guard: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_sanitization_and_no_leak()
    test_injection_vector_neutralized_and_block_signal()
    test_observer_only_static_guard()
    print("test_phase11_audit: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
