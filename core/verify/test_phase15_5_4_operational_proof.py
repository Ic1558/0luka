#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_dod(tmp: Path, commit_sha: str) -> Path:
    dod_dir = tmp / "docs" / "dod"
    dod_dir.mkdir(parents=True, exist_ok=True)
    dod = dod_dir / "DOD__PHASE_15_5_3.md"
    dod.write_text(
        "\n".join(
            [
                "# DoD — PHASE_15_5_3",
                "",
                "## 0. Metadata (MANDATORY)",
                "- **Phase / Task ID**: PHASE_15_5_3",
                "- **Gate**: G1",
                "- **Related SOT Section**: §Tier1.Phase15.5.3",
                f"- **Commit SHA**: {commit_sha}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return dod_dir


def _write_phase_status(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """phases:
  PHASE_15_5_3:
    verdict: DESIGNED
    requires:
""",
        encoding="utf-8",
    )


def _run_checker(tmp: Path, feed: Path) -> subprocess.CompletedProcess:
    commit_sha = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True).strip()
    )
    dod_dir = _write_dod(tmp, commit_sha)
    phase_status = tmp / "phase_status.yaml"
    _write_phase_status(phase_status)
    env = os.environ.copy()
    env["DOD_ROOT"] = str(REPO_ROOT)
    env["DOD_DOCS_DIR"] = str(dod_dir)
    env["DOD_PHASE_STATUS_PATH"] = str(phase_status)
    env["DOD_REPORTS_DIR"] = str(tmp / "dod_reports")
    env["LUKA_ACTIVITY_FEED_JSONL"] = str(feed)
    env["LUKA_REQUIRE_OPERATIONAL_PROOF"] = "1"
    return subprocess.run(
        [sys.executable, "tools/ops/dod_checker.py", "--phase", "PHASE_15_5_3", "--json"],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
    )


def test_operational_chain_from_monitor_is_accepted() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity_feed.jsonl"
        feed.parent.mkdir(parents=True, exist_ok=True)
        feed.write_text("", encoding="utf-8")

        env = os.environ.copy()
        env["ROOT"] = str(REPO_ROOT)
        env["LUKA_ACTIVITY_FEED_JSONL"] = str(feed)
        env["LUKA_IDLE_DRIFT_REPORT_DIR"] = str(tmp / "idle_reports")
        proc_monitor = subprocess.run(
            [sys.executable, "tools/ops/idle_drift_monitor.py", "--once", "--json"],
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
        )
        assert proc_monitor.returncode in (0, 2), proc_monitor.stdout + proc_monitor.stderr

        proc = _run_checker(tmp, feed)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        payload = json.loads(proc.stdout)
        result = payload["results"][0]
        assert result["verdict"] == "PROVEN"
        assert result["checks"]["activity_chain"]["proof_mode"] == "operational"


def test_synthetic_chain_rejected_when_operational_required() -> None:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity_feed.jsonl"
        evidence = tmp / "evidence.json"
        evidence.write_text('{"ok":true}\n', encoding="utf-8")

        rows = []
        for i, action in enumerate(["started", "completed", "verified"]):
            t = now + timedelta(seconds=i)
            row = {
                "ts_utc": _iso(t),
                "ts_epoch_ms": int(t.timestamp() * 1000),
                "phase_id": "PHASE_15_5_3",
                "action": action,
                "emit_mode": "manual_append",
                "verifier_mode": "synthetic_proof",
                "tool": "idle_drift_monitor",
                "run_id": "r1",
                "evidence": [str(evidence)],
            }
            rows.append(row)
        _write_jsonl(feed, rows)

        proc = _run_checker(tmp, feed)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        result = json.loads(proc.stdout)["results"][0]
        assert result["verdict"] == "PARTIAL"
        assert "proof.synthetic_not_allowed" in result["missing"]


def test_missing_taxonomy_keys_flagged() -> None:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity_feed.jsonl"
        evidence = tmp / "evidence.json"
        evidence.write_text('{"ok":true}\n', encoding="utf-8")

        rows = []
        for i, action in enumerate(["started", "completed", "verified"]):
            t = now + timedelta(seconds=i)
            row = {
                "ts_utc": _iso(t),
                "ts_epoch_ms": int(t.timestamp() * 1000),
                "phase_id": "PHASE_15_5_3",
                "action": action,
                "emit_mode": "runtime_auto",
                "verifier_mode": "operational_proof",
                "tool": "idle_drift_monitor",
                "evidence": [str(evidence)],
            }
            rows.append(row)
        _write_jsonl(feed, rows)

        proc = _run_checker(tmp, feed)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        result = json.loads(proc.stdout)["results"][0]
        assert result["verdict"] == "PARTIAL"
        assert "taxonomy.incomplete_event" in result["missing"]


def test_parse_failure_exits_4_in_operational_mode() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity_feed.jsonl"
        feed.write_text("{bad json}\n", encoding="utf-8")
        proc = _run_checker(tmp, feed)
        assert proc.returncode == 4, proc.stdout + proc.stderr


if __name__ == "__main__":
    test_operational_chain_from_monitor_is_accepted()
    test_synthetic_chain_rejected_when_operational_required()
    test_missing_taxonomy_keys_flagged()
    print("test_phase15_5_4_operational_proof: all ok")
