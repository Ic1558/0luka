#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _latest_export_dir(runtime_root: Path) -> Path | None:
    exports_dir = runtime_root / "exports"
    if not exports_dir.exists() or not exports_dir.is_dir():
        return None
    candidates = [
        path
        for path in exports_dir.iterdir()
        if path.is_dir() and path.name.startswith("ledger_proof_")
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.name)[-1]


def _run_json_command(args: list[str], *, env: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    stream = proc.stdout.strip() or proc.stderr.strip()
    if not stream:
        raise RuntimeError(f"empty_output:{' '.join(args)}")
    try:
        payload = json.loads(stream)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_json:{' '.join(args)}:{exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{' '.join(args)}")
    return proc.returncode, payload


def _health_summary(report: dict[str, Any]) -> dict[str, Any]:
    tests = report.get("tests") if isinstance(report.get("tests"), dict) else {}
    passed = tests.get("passed")
    total = tests.get("suites")
    status = str(report.get("status", "")).upper() if report.get("status") else "FAILED"
    return {
        "status": status,
        "passed": passed if isinstance(passed, int) else None,
        "total": total if isinstance(total, int) else None,
        "ok": status == "HEALTHY",
    }


def _watchdog_summary(report: dict[str, Any]) -> dict[str, Any]:
    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    return {
        "ok": bool(report.get("ok")),
        "checks": {
            "active_feed": checks.get("active_feed"),
            "epoch_manifest": checks.get("epoch_manifest"),
            "rotated_feeds": checks.get("rotated_feeds"),
            "segment_integrity": checks.get("segment_integrity"),
            "segment_chain": checks.get("segment_chain"),
            "ledger_root": checks.get("ledger_root"),
        },
    }


def _proof_summary(runtime_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    export_dir = _latest_export_dir(runtime_root)
    if export_dir is None:
        return {
            "available": False,
            "path": None,
            "ok": False,
            "status": "UNAVAILABLE",
            "epoch_id": None,
            "leaf_count": None,
            "segment_seq_min": None,
            "segment_seq_max": None,
            "merkle_root": None,
        }, [{"error": "proof_pack_unavailable"}]

    rc, payload = _run_json_command(
        [sys.executable, "tools/ops/proof_report.py", "--path", str(export_dir), "--json"]
    )
    summary = {
        "available": True,
        "path": str(export_dir),
        "ok": bool(payload.get("ok")) and rc == 0,
        "status": "VERIFIED" if bool(payload.get("ok")) and rc == 0 else "FAILED",
        "epoch_id": payload.get("epoch_id"),
        "leaf_count": payload.get("leaf_count"),
        "segment_seq_min": payload.get("segment_seq_min"),
        "segment_seq_max": payload.get("segment_seq_max"),
        "merkle_root": payload.get("merkle_root"),
    }
    errors = payload.get("errors")
    if isinstance(errors, list):
        return summary, errors
    return summary, []


def _overall_status(system_health: dict[str, Any], ledger_watchdog: dict[str, Any], proof_pack: dict[str, Any]) -> str:
    if not bool(system_health.get("ok")):
        return "FAILED"
    if not bool(ledger_watchdog.get("ok")):
        return "FAILED"
    if not bool(proof_pack.get("available")):
        return "DEGRADED"
    if not bool(proof_pack.get("ok")):
        return "FAILED"
    return "HEALTHY"


def build_runtime_status_report() -> dict[str, Any]:
    runtime_root = _runtime_root()
    env = os.environ.copy()
    env["LUKA_RUNTIME_ROOT"] = str(runtime_root)

    health_rc, health_payload = _run_json_command([sys.executable, "core/health.py", "--full", "--json"], env=env)
    watchdog_rc, watchdog_payload = _run_json_command(
        [
            sys.executable,
            "tools/ops/ledger_watchdog.py",
            "--check-epoch",
            "--json",
            "--no-report",
            "--no-emit",
        ],
        env=env,
    )

    system_health = _health_summary(health_payload)
    if health_rc != 0:
        system_health["ok"] = False
        if system_health["status"] == "HEALTHY":
            system_health["status"] = "FAILED"

    ledger_watchdog = _watchdog_summary(watchdog_payload)
    if watchdog_rc != 0:
        ledger_watchdog["ok"] = False

    proof_pack, proof_errors = _proof_summary(runtime_root)
    overall_status = _overall_status(system_health, ledger_watchdog, proof_pack)

    errors: list[dict[str, Any]] = []
    if not bool(system_health.get("ok")):
        errors.append({"error": "system_health_failed"})
    if not bool(ledger_watchdog.get("ok")):
        errors.append({"error": "ledger_watchdog_failed"})
    if not bool(proof_pack.get("available")):
        errors.append({"error": "proof_pack_unavailable"})
    elif not bool(proof_pack.get("ok")):
        errors.append({"error": "proof_pack_failed"})
    errors.extend(item for item in proof_errors if isinstance(item, dict))

    return {
        "ok": overall_status == "HEALTHY",
        "system_health": {
            "status": system_health["status"],
            "passed": system_health.get("passed"),
            "total": system_health.get("total"),
        },
        "ledger_watchdog": ledger_watchdog,
        "proof_pack": {
            "available": proof_pack["available"],
            "path": proof_pack["path"],
            "ok": proof_pack["ok"],
            "epoch_id": proof_pack["epoch_id"],
            "leaf_count": proof_pack["leaf_count"],
            "segment_seq_min": proof_pack["segment_seq_min"],
            "segment_seq_max": proof_pack["segment_seq_max"],
            "merkle_root": proof_pack["merkle_root"],
        },
        "overall_status": overall_status,
        "errors": errors,
    }


def _status_label(ok: bool | None) -> str:
    return "OK" if bool(ok) else "FAILED"


def _segment_range(proof_pack: dict[str, Any]) -> str:
    low = proof_pack.get("segment_seq_min")
    high = proof_pack.get("segment_seq_max")
    if isinstance(low, int) and isinstance(high, int):
        return f"{low}-{high}"
    return "n/a"


def render_runtime_status_report(report: dict[str, Any]) -> str:
    system_health = report["system_health"]
    ledger_watchdog = report["ledger_watchdog"]
    proof_pack = report["proof_pack"]
    checks = ledger_watchdog.get("checks") if isinstance(ledger_watchdog.get("checks"), dict) else {}
    lines = [
        "0luka Runtime Status Report",
        "",
        "System Health",
        f"  status: {system_health.get('status', 'FAILED')}",
        f"  passed: {system_health.get('passed')}/{system_health.get('total')}",
        "",
        "Ledger Watchdog",
        f"  status: {_status_label(ledger_watchdog.get('ok'))}",
        f"  active_feed: {_status_label((checks.get('active_feed') or {}).get('ok') if isinstance(checks.get('active_feed'), dict) else False)}",
        f"  epoch_manifest: {_status_label((checks.get('epoch_manifest') or {}).get('ok') if isinstance(checks.get('epoch_manifest'), dict) else False)}",
        f"  rotated_feeds: {_status_label((checks.get('rotated_feeds') or {}).get('ok') if isinstance(checks.get('rotated_feeds'), dict) else False)}",
        f"  segment_integrity: {_status_label((checks.get('segment_integrity') or {}).get('ok') if isinstance(checks.get('segment_integrity'), dict) else False)}",
        f"  segment_chain: {_status_label((checks.get('segment_chain') or {}).get('ok') if isinstance(checks.get('segment_chain'), dict) else False)}",
        f"  ledger_root: {_status_label((checks.get('ledger_root') or {}).get('ok') if isinstance(checks.get('ledger_root'), dict) else False)}",
        "",
        "Proof Pack",
        f"  latest_export: {proof_pack.get('path') if proof_pack.get('path') else 'unavailable'}",
        f"  proof_status: {'VERIFIED' if proof_pack.get('available') and proof_pack.get('ok') else ('FAILED' if proof_pack.get('available') else 'UNAVAILABLE')}",
        f"  epoch_id: {proof_pack.get('epoch_id') if proof_pack.get('epoch_id') is not None else 'n/a'}",
        f"  leaf_count: {proof_pack.get('leaf_count') if proof_pack.get('leaf_count') is not None else 'n/a'}",
        f"  segment_range: {_segment_range(proof_pack)}",
        f"  merkle_root: {proof_pack.get('merkle_root') if proof_pack.get('merkle_root') else 'n/a'}",
        "",
        "Overall",
        f"  result: {report.get('overall_status', 'FAILED')}",
    ]
    return "\n".join(lines)


def _exit_code(report: dict[str, Any]) -> int:
    overall = report.get("overall_status")
    if overall == "HEALTHY":
        return 0
    if overall == "DEGRADED":
        return 2
    if overall == "FAILED":
        return 3
    return 4


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an operator runtime status report.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    try:
        report = build_runtime_status_report()
    except Exception as exc:
        payload = {
            "ok": False,
            "system_health": {"status": "FAILED", "passed": None, "total": None},
            "ledger_watchdog": {"ok": False, "checks": {}},
            "proof_pack": {
                "available": False,
                "path": None,
                "ok": False,
                "epoch_id": None,
                "leaf_count": None,
                "segment_seq_min": None,
                "segment_seq_max": None,
                "merkle_root": None,
            },
            "overall_status": "FAILED",
            "errors": [{"error": f"report_generation_failed:{exc}"}],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(render_runtime_status_report(payload))
        return 4

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(render_runtime_status_report(report))
    return _exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
