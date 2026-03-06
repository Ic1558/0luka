#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.verify_exported_proof import verify_exported_proof

CHECK_ORDER = (
    "checksums",
    "segment_chain",
    "epoch_manifest",
    "registry_seals",
    "ledger_root",
)
MISSING_FAILURES = {
    "missing_export_dir",
    "missing_required_file",
    "invalid_export_metadata",
}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{path}")
    return payload


def _first_reason(report: dict[str, Any]) -> str | None:
    first_failure = report.get("first_failure")
    if isinstance(first_failure, str) and first_failure in MISSING_FAILURES:
        return first_failure
    errors = report.get("errors")
    if not isinstance(errors, list) or not errors:
        return first_failure if isinstance(first_failure, str) else None
    first = errors[0]
    if not isinstance(first, dict):
        return str(first)
    check = first.get("check")
    error = first.get("error")
    if isinstance(check, str) and isinstance(error, str):
        return f"{check}:{error}"
    if isinstance(error, str):
        return error
    if isinstance(check, str):
        return check
    return first_failure if isinstance(first_failure, str) else None


def _build_verdict(report: dict[str, Any], proof_pack: Path) -> dict[str, Any]:
    ledger_root_path = proof_pack / "logs" / "ledger_root.json"
    ledger_root: dict[str, Any] = {}
    if ledger_root_path.exists() and ledger_root_path.is_file():
        try:
            ledger_root = _read_json(ledger_root_path)
        except Exception:
            ledger_root = {}

    epoch_anchor = ledger_root.get("epoch_anchor")
    epoch_id = epoch_anchor.get("epoch_id") if isinstance(epoch_anchor, dict) else None

    return {
        "ok": bool(report.get("ok")),
        "proof_pack": str(proof_pack),
        "epoch_id": epoch_id,
        "leaf_count": ledger_root.get("leaf_count"),
        "segment_seq_min": ledger_root.get("segment_seq_min"),
        "segment_seq_max": ledger_root.get("segment_seq_max"),
        "merkle_root": ledger_root.get("merkle_root"),
        "checks": report.get("checks", {}),
        "first_failure": report.get("first_failure"),
        "errors": report.get("errors", []),
    }


def _render_check_line(name: str, payload: dict[str, Any]) -> str:
    marker = "✓" if bool(payload.get("ok")) else "x"
    return f"  {marker} {name}"


def _render_report(verdict: dict[str, Any]) -> str:
    segment_min = verdict.get("segment_seq_min")
    segment_max = verdict.get("segment_seq_max")
    if isinstance(segment_min, int) and isinstance(segment_max, int):
        segment_range = f"{segment_min}-{segment_max}"
    else:
        segment_range = "unknown"

    lines = [
        "0luka Ledger Proof Verification",
        "Proof Pack",
        f"  path: {verdict['proof_pack']}",
        "",
        "Ledger State",
        f"  epoch_id: {verdict.get('epoch_id') if verdict.get('epoch_id') is not None else 'unknown'}",
        f"  leaf_count: {verdict.get('leaf_count') if verdict.get('leaf_count') is not None else 'unknown'}",
        f"  segment_range: {segment_range}",
        f"  merkle_root: {verdict.get('merkle_root') if verdict.get('merkle_root') else 'unknown'}",
        "",
        "Checks",
    ]
    checks = verdict.get("checks")
    for name in CHECK_ORDER:
        payload = checks.get(name) if isinstance(checks, dict) else None
        if isinstance(payload, dict):
            lines.append(_render_check_line(name, payload))
        else:
            lines.append(f"  - {name} (not_run)")

    lines.extend(["", "Result"])
    if verdict.get("ok"):
        lines.append("  VERIFIED")
    else:
        lines.append("  FAILED")
        first_failure = verdict.get("first_failure")
        if isinstance(first_failure, str):
            lines.append(f"  first_failure: {first_failure}")
        reason = _first_reason(verdict)
        if isinstance(reason, str):
            lines.append(f"  reason: {reason}")
    return "\n".join(lines)


def _exit_code(verdict: dict[str, Any]) -> int:
    if verdict.get("ok"):
        return 0
    first_failure = verdict.get("first_failure")
    if isinstance(first_failure, str) and first_failure in MISSING_FAILURES:
        return 3
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a human or JSON report for an exported ledger proof pack.")
    parser.add_argument("--path", type=Path, required=True, help="Export directory path")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON verdict")
    args = parser.parse_args()

    proof_pack = args.path.expanduser().resolve()
    try:
        report = verify_exported_proof(proof_pack)
        verdict = _build_verdict(report, proof_pack)
        rc = _exit_code(verdict)
    except Exception as exc:
        payload = {
            "ok": False,
            "proof_pack": str(proof_pack),
            "epoch_id": None,
            "leaf_count": None,
            "segment_seq_min": None,
            "segment_seq_max": None,
            "merkle_root": None,
            "checks": {},
            "first_failure": "report_generation_failed",
            "errors": [{"error": f"report_generation_failed:{exc}"}],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(_render_report(payload))
        return 4

    if args.json:
        print(json.dumps(verdict, ensure_ascii=False))
    else:
        print(_render_report(verdict))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
