#!/usr/bin/env python3
"""Phase 14 learning metrics collector (isolated analytics, non-binding proposals)."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _repo_root() -> Path:
    import os

    raw = os.environ.get("ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve(strict=False)
    return Path(__file__).resolve().parents[3]


def _activity_path(root: Path) -> Path:
    return root / "observability" / "activity" / "activity.jsonl"


def _annotations_path(root: Path) -> Path:
    return root / "observability" / "annotations" / "annotations.jsonl"


def _metrics_path(root: Path) -> Path:
    return root / "observability" / "metrics" / "phase14" / "system_kpis.jsonl"


def _recommendations_path(root: Path) -> Path:
    return root / "observability" / "recommendations" / "policy_suggestions.jsonl"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _event_id(row: Dict[str, Any]) -> str:
    return str(row.get("activity_id") or row.get("event_id") or row.get("task_id") or "")


def _is_blocked_activity(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("level") or "").lower()
    narrative = str(row.get("narrative") or row.get("message") or "").lower()
    etype = str(row.get("type") or "").lower()
    if status in {"requires-human-attention", "blocked", "rejected"}:
        return True
    if any(x in narrative for x in ("blocked", "rejected", "denied", "escalate")):
        return True
    if any(x in etype for x in ("blocked", "violation", "human.escalate")):
        return True
    return False


def _targeted_gate(activity_rows: List[Dict[str, Any]], annotations: List[Dict[str, Any]]) -> str:
    corpus = " ".join(
        [str(r.get("narrative") or r.get("message") or "") for r in activity_rows]
        + [str(a.get("comment") or "") for a in annotations]
    ).lower()
    if any(k in corpus for k in ("sentry", "blocked", "violation")):
        return "sentry"
    if any(k in corpus for k in ("ambiguous", "clarify", "linguist")):
        return "linguist"
    return "dispatcher"


def collect_metrics() -> Dict[str, Any]:
    root = _repo_root()
    activities = _read_jsonl(_activity_path(root))
    annotations = _read_jsonl(_annotations_path(root))

    event_ids = [eid for eid in (_event_id(r) for r in activities) if eid]
    total_events = len(event_ids)
    unique_ids = set(event_ids)

    acknowledged_ids = {
        str(a.get("event_id") or "")
        for a in annotations
        if str(a.get("action") or "").lower() == "acknowledge" and str(a.get("event_id") or "")
    }
    aligned_count = len(unique_ids.intersection(acknowledged_ids))
    alignment_rate = round((aligned_count / max(1, len(unique_ids))) * 100.0, 2)

    blocked_count = sum(1 for row in activities if _is_blocked_activity(row))
    block_rate = round((blocked_count / max(1, total_events)) * 100.0, 2)

    disagree_rows = [a for a in annotations if str(a.get("action") or "").lower() == "disagree"]
    disagreement_rate = round((len(disagree_rows) / max(1, len(annotations))) * 100.0, 2)

    ts = _utc_now()
    metrics_rows = [
        {
            "schema_version": "system_metrics.v1",
            "ts": ts,
            "kpi_type": "alignment",
            "value": alignment_rate,
            "metadata": {"aligned": aligned_count, "total_events": len(unique_ids)},
        },
        {
            "schema_version": "system_metrics.v1",
            "ts": ts,
            "kpi_type": "block_rate",
            "value": block_rate,
            "metadata": {"blocked": blocked_count, "total_tasks": total_events},
        },
        {
            "schema_version": "system_metrics.v1",
            "ts": ts,
            "kpi_type": "triage_velocity",
            "value": round(alignment_rate - disagreement_rate, 2),
            "metadata": {"disagreement_rate": disagreement_rate, "annotations": len(annotations)},
        },
    ]

    for row in metrics_rows:
        _append_jsonl(_metrics_path(root), row)

    proposals = 0
    if disagreement_rate >= 30.0:
        targeted_gate = _targeted_gate(activities, disagree_rows)
        evidence_refs = [str(a.get("event_id") or "") for a in disagree_rows if str(a.get("event_id") or "")]
        proposal = {
            "schema_version": "policy_proposal.v1",
            "proposal_id": f"proposal_{uuid.uuid4().hex[:12]}",
            "ts": ts,
            "targeted_gate": targeted_gate,
            "suggested_change": f"Review threshold tuning for {targeted_gate}; disagreement_rate={disagreement_rate}%",
            "evidence_refs": evidence_refs[:20],
        }
        _append_jsonl(_recommendations_path(root), proposal)
        proposals += 1

    return {
        "ts": ts,
        "activities": len(activities),
        "annotations": len(annotations),
        "alignment_rate": alignment_rate,
        "block_rate": block_rate,
        "disagreement_rate": disagreement_rate,
        "proposals_written": proposals,
        "metrics_path": str(_metrics_path(root)),
        "recommendations_path": str(_recommendations_path(root)),
    }


if __name__ == "__main__":
    result = collect_metrics()
    print(json.dumps(result, ensure_ascii=False, indent=2))
