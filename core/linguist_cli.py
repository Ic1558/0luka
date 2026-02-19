#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:
    yaml = None

from core.sentry import SentryViolation, run_preflight


def _default_root() -> Path:
    raw = os.environ.get("ROOT")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _fixture_path(root: Path) -> Path:
    return root / "modules" / "nlp_control_plane" / "tests" / "phase9_vectors_v0.yaml"


def _fake_runner_ok(cmd: list[str], capture_output: bool = True, text: bool = True):
    return subprocess.CompletedProcess(cmd, 0, stdout="state = running", stderr="")


def _runner_from_env() -> Callable[..., subprocess.CompletedProcess]:
    mode = os.environ.get("LINGUIST_CLI_RUNNER", "").strip().lower()
    if mode == "ok":
        return _fake_runner_ok
    return subprocess.run


def _load_fixture(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml_missing")
    if not path.exists():
        raise RuntimeError(f"fixture_missing:{path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("fixture_invalid")
    return data


def _normalize_input(raw: str) -> str:
    return raw.strip()


def _match_vectors(data: dict[str, Any], text: str) -> tuple[str, dict[str, Any]]:
    vectors = data.get("vectors") if isinstance(data.get("vectors"), list) else []
    matches = [v for v in vectors if isinstance(v, dict) and str(v.get("input", "")).strip() == text]

    if len(matches) > 1:
        return "ambiguous", {"reason": "ambiguous_mapping"}
    if len(matches) == 1:
        v = matches[0]
        return "ok", {
            "intent": v.get("expected_intent"),
            "slots": v.get("required_slots", {}),
            "vector_id": v.get("id"),
        }

    fail_closed = data.get("fail_closed_cases") if isinstance(data.get("fail_closed_cases"), list) else []
    for row in fail_closed:
        if isinstance(row, dict) and str(row.get("input", "")).strip() == text:
            return "needs_clarification", {
                "reason": row.get("reason", "needs_clarification"),
                "expected_result": "needs_clarification",
                "vector_id": row.get("id"),
            }

    return "needs_clarification", {
        "reason": "no_exact_match",
        "expected_result": "needs_clarification",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Linguist CLI v0 (dry mapping only)")
    parser.add_argument("--input", type=str, help="NLP input text")
    args = parser.parse_args()

    text = _normalize_input(args.input or "")
    if not text:
        text = _normalize_input(sys.stdin.read())

    trace = f"trace_{uuid.uuid4().hex}"
    root = _default_root()

    runner = _runner_from_env()
    try:
        run_preflight(
            root=root,
            require_activity_feed=True,
            probe_dispatcher=True,
            runner=runner,
        )
    except SentryViolation as exc:
        print(json.dumps({"ok": False, "error": f"sentry_violation:{exc}", "trace": trace}, ensure_ascii=False))
        return 1

    if not text:
        print(
            json.dumps(
                {"ok": False, "expected_result": "needs_clarification", "reason": "empty_input", "trace": trace},
                ensure_ascii=False,
            )
        )
        return 2

    try:
        fixture = _load_fixture(_fixture_path(root))
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "trace": trace}, ensure_ascii=False))
        return 1

    status, payload = _match_vectors(fixture, text)
    if status == "ok":
        print(
            json.dumps(
                {
                    "ok": True,
                    "intent": payload["intent"],
                    "slots": payload["slots"],
                    "vector_id": payload["vector_id"],
                    "trace": trace,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if status in {"needs_clarification", "ambiguous"}:
        print(
            json.dumps(
                {
                    "ok": False,
                    "expected_result": "needs_clarification",
                    "reason": payload.get("reason", "needs_clarification"),
                    "vector_id": payload.get("vector_id"),
                    "trace": trace,
                },
                ensure_ascii=False,
            )
        )
        return 2

    print(json.dumps({"ok": False, "error": "unexpected_state", "trace": trace}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
