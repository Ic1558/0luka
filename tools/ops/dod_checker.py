#!/usr/bin/env python3
"""
DoD Auto-Checker (Phase 2 proof engine)

Usage:
  python3 tools/ops/dod_checker.py --phase <ID>
  python3 tools/ops/dod_checker.py --all
  python3 tools/ops/dod_checker.py --json
  python3 tools/ops/dod_checker.py --missing-only
  python3 tools/ops/dod_checker.py --update-status
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

BLUEPRINT_KEY = "blueprint_ppr_dod_agentteams_v2_r1_tighten"
BLUEPRINT_REV = "Rev1.3"
VERDICT_DESIGNED = "DESIGNED"
VERDICT_PARTIAL = "PARTIAL"
VERDICT_PROVEN = "PROVEN"

EMIT_MODE_MANUAL = "manual_append"
EMIT_MODE_TOOL = "tool_wrapped"
EMIT_MODE_AUTO = "runtime_auto"

PROOF_MODE_SYNTHETIC = "synthetic"
PROOF_MODE_OPERATIONAL = "operational"
PHASE_OPERATIONAL_TARGET = "PHASE_15_5_3"

REQUIRED_TAXONOMY_KEYS = (
    "phase_id",
    "emit_mode",
    "verifier_mode",
    "tool",
    "run_id",
    "ts_epoch_ms",
    "ts_utc",
)


@dataclass(frozen=True)
class Paths:
    root: Path
    docs_dod: Path
    reports_dir: Path
    activity_feed: Path
    phase_status: Path


@dataclass(frozen=True)
class EvidencePathRef:
    raw: str
    path: Path
    traversal: bool


def _resolve_root() -> Path:
    env_root = os.environ.get("DOD_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve(strict=False)
    return Path(__file__).resolve().parents[2]


def resolve_paths() -> Paths:
    root = _resolve_root()
    docs_dod = Path(os.environ.get("DOD_DOCS_DIR", str(root / "docs/dod"))).expanduser().resolve(strict=False)
    reports_dir = Path(
        os.environ.get("DOD_REPORTS_DIR", str(root / "observability/reports/dod_checker"))
    ).expanduser().resolve(strict=False)
    activity_raw = os.environ.get("LUKA_ACTIVITY_FEED_JSONL", str(root / "observability/logs/activity_feed.jsonl"))
    if ".." in Path(activity_raw.replace("\\", "/")).parts:
        raise RuntimeError(f"activity_feed_path_traversal:{activity_raw}")
    activity_feed = Path(activity_raw).expanduser().resolve(strict=False)
    phase_status = Path(
        os.environ.get("DOD_PHASE_STATUS_PATH", str(root / "core/governance/phase_status.yaml"))
    ).expanduser().resolve(strict=False)
    return Paths(root=root, docs_dod=docs_dod, reports_dir=reports_dir, activity_feed=activity_feed, phase_status=phase_status)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        # Handle epoch ms
        if ts > 10**12: # likely ms
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    
    if not isinstance(ts, str) or not ts.strip():
        return None
    raw = ts.strip()
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _has_path_traversal(raw_path: str) -> bool:
    raw = str(raw_path).strip()
    if not raw:
        return False
    candidate = raw.replace("\\", "/")
    return candidate == ".." or candidate.startswith("../") or candidate.endswith("/..") or "/../" in f"/{candidate}/"


def _git_commit_exists(paths: Paths, commit_sha: str) -> bool:
    if not isinstance(commit_sha, str) or not commit_sha.strip():
        return False
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit_sha.strip()}^{{commit}}"],
            cwd=str(paths.root),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def parse_dod_metadata(file_path: Path) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    if not file_path.exists():
        return meta
    text = file_path.read_text(encoding="utf-8")
    fields = {
        "phase_id": r"- \*\*Phase / Task ID\*\*: (.+)",
        "commit_sha": r"- \*\*Commit SHA\*\*: (.+)",
        "gate": r"- \*\*Gate\*\*: (.+)",
        "related_sot": r"- \*\*Related SOT Section\*\*: (.+)",
    }
    for key, pattern in fields.items():
        m = re.search(pattern, text)
        if m:
            meta[key] = m.group(1).strip()
    return meta


def _parse_jsonl(path: Path, *, strict: bool = False) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not path.exists():
        return events
    with path.open("r", encoding="utf-8") as handle:
        for ln in handle:
            line = ln.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                if strict:
                    raise RuntimeError(f"activity_feed_parse_failure:{path}:{exc}") from exc
                continue
            if isinstance(payload, dict):
                events.append(payload)
    return events


def _event_phase_match(event: Dict[str, Any], phase_id: str) -> bool:
    phase = str(event.get("phase_id") or event.get("phase") or "").strip()
    if phase == phase_id:
        return True
    # fallback: match explicit metadata key used by some emitters
    return str(event.get("task_id") or "").strip() == phase_id


def _pick_latest_chain(events: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    items: List[Tuple[datetime, Dict[str, Any]]] = []
    for e in events:
        ts = _parse_iso(e.get("ts") or e.get("ts_utc") or e.get("timestamp"))
        if ts is not None:
            items.append((ts, e))
    items.sort(key=lambda x: x[0])

    best: Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]] = (None, None, None)
    for i, (_, started_evt) in enumerate(items):
        if str(started_evt.get("action", "")).lower() != "started":
            continue
        completed_evt = None
        verified_evt = None
        for _, evt2 in items[i + 1 :]:
            a2 = str(evt2.get("action", "")).lower()
            if completed_evt is None and a2 == "completed":
                completed_evt = evt2
                continue
            if completed_evt is not None and a2 == "verified":
                verified_evt = evt2
                break
        if completed_evt is None:
            if best == (None, None, None):
                best = (started_evt, None, None)
            continue
        if verified_evt is None:
            best = (started_evt, completed_evt, None)
            continue
        best = (started_evt, completed_evt, verified_evt)
    return best


def _get_ts(evt: Dict[str, Any]) -> Optional[datetime]:
    if not evt:
        return None
    # prioritize epoch ms for high resolution
    if "ts_epoch_ms" in evt:
        val = evt["ts_epoch_ms"]
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(val / 1000, tz=timezone.utc)
    if "timestamp" in evt and isinstance(evt["timestamp"], (int, float)):
        return _parse_iso(evt["timestamp"])
    return _parse_iso(evt.get("ts") or evt.get("ts_utc") or evt.get("timestamp"))


def _latest_event_by_action(events: List[Dict[str, Any]], action: str) -> Optional[Dict[str, Any]]:
    target = action.lower()
    best_evt: Optional[Dict[str, Any]] = None
    best_ts: Optional[datetime] = None
    for evt in events:
        if str(evt.get("action", "")).lower() != target:
            continue
        ts = _get_ts(evt)
        if ts is None:
            continue
        if best_ts is None or ts > best_ts:
            best_ts = ts
            best_evt = evt
    return best_evt


def _event_taxonomy_missing(event: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(event, dict) or not event:
        return list(REQUIRED_TAXONOMY_KEYS)
    return [k for k in REQUIRED_TAXONOMY_KEYS if k not in event]


def check_activity_events(
    phase_id: str,
    paths: Paths,
    *,
    strict_parse: bool = False,
    enforce_operational_taxonomy: bool = False,
) -> Dict[str, Any]:
    all_events = _parse_jsonl(paths.activity_feed, strict=strict_parse)
    phase_events = [e for e in all_events if _event_phase_match(e, phase_id)]
    started_evt, completed_evt, verified_evt = _pick_latest_chain(phase_events)
    latest_started = _latest_event_by_action(phase_events, "started")
    latest_completed = _latest_event_by_action(phase_events, "completed")
    latest_verified = _latest_event_by_action(phase_events, "verified")

    started_ts = _get_ts(started_evt or {})
    completed_ts = _get_ts(completed_evt or {})
    verified_ts = _get_ts(verified_evt or {})
    latest_started_ts = _get_ts(latest_started or {})
    latest_completed_ts = _get_ts(latest_completed or {})
    latest_verified_ts = _get_ts(latest_verified or {})

    order_ok = bool(started_ts and completed_ts and verified_ts and started_ts < completed_ts < verified_ts)
    latest_order_ok = bool(
        latest_started_ts and latest_completed_ts and latest_verified_ts and latest_started_ts < latest_completed_ts < latest_verified_ts
    )

    missing: List[str] = []
    if latest_started is None:
        missing.append("activity.started")
    if latest_completed is None:
        missing.append("activity.completed")
    if latest_verified is None:
        missing.append("activity.verified")
    if latest_started and latest_completed and latest_verified and not latest_order_ok:
        missing.append("activity.order_invalid")

    evts = [started_evt, completed_evt, verified_evt]
    taxonomy_missing = []
    if enforce_operational_taxonomy:
        for evt in evts:
            taxonomy_missing.extend(_event_taxonomy_missing(evt))
    modes = [e.get("emit_mode") for e in evts if e]
    verifier_modes = [e.get("verifier_mode") for e in evts if e]
    is_operational = (
        len(modes) == 3
        and all(m == EMIT_MODE_AUTO for m in modes)
        and len(verifier_modes) == 3
        and all(v == "operational_proof" for v in verifier_modes)
        and not taxonomy_missing
    )
    proof_mode = PROOF_MODE_OPERATIONAL if is_operational else PROOF_MODE_SYNTHETIC

    # 3. Activity Feed Audit Enhancer: Flag missing taxonomy
    taxonomy_ok = True
    for e in evts:
        if not e:
            continue
        missing_keys = [k for k in ("emit_mode", "verifier_mode", "ts_epoch_ms", "tool", "run_id") if k not in e]
        if missing_keys:
            taxonomy_ok = False
            break

    # 4. Consistency Check: run_id must match across chain
    if taxonomy_ok and is_operational:
        run_ids = {e.get("run_id") for e in evts if e}
        if len(run_ids) > 1:
            taxonomy_ok = False
            missing.append("taxonomy.run_id_mismatch")
    if not taxonomy_ok:
        missing.append("taxonomy.incomplete_event")

    return {
        "started": latest_started is not None,
        "completed": latest_completed is not None,
        "verified": latest_verified is not None,
        "order_ok": order_ok,
        "latest_order_ok": latest_order_ok,
        "chain_valid": latest_order_ok,
        "proof_mode": proof_mode,
        "events": {
            "started": started_evt,
            "completed": completed_evt,
            "verified": verified_evt,
        },
        "taxonomy_missing": sorted(set(taxonomy_missing)),
        "event_count": len(phase_events),
        "missing": missing,
        "taxonomy_ok": taxonomy_ok,
    }


def _collect_evidence_paths(meta_file: Path, chain_events: Iterable[Dict[str, Any]], root: Path) -> List[EvidencePathRef]:
    out: List[EvidencePathRef] = []

    for evt in chain_events:
        ev = evt.get("evidence", [])
        raw_paths = []
        if isinstance(ev, list):
            raw_paths = [p for p in ev if isinstance(p, str)]
        elif isinstance(ev, dict):
            # Handle standard feed dict evidence
            for k in ("file", "path", "report"):
                if isinstance(ev.get(k), str):
                    raw_paths.append(ev[k])
        elif isinstance(ev, str):
            raw_paths = [ev]

        for p in raw_paths:
            if p.strip():
                raw = p.strip()
                q = Path(raw)
                out.append(
                    EvidencePathRef(
                        raw=raw,
                        path=(q if q.is_absolute() else (root / q)),
                        traversal=_has_path_traversal(raw),
                    )
                )

    if meta_file.exists():
        text = meta_file.read_text(encoding="utf-8")
        for m in re.finditer(r"(?:path|file):\s*([^\s]+)", text):
            raw = m.group(1).strip()
            q = Path(raw)
            out.append(
                EvidencePathRef(
                    raw=raw,
                    path=(q if q.is_absolute() else (root / q)),
                    traversal=_has_path_traversal(raw),
                )
            )
    # unique preserve order
    dedup: List[EvidencePathRef] = []
    seen = set()
    for p in out:
        key = (p.raw, str(p.path))
        if key not in seen:
            seen.add(key)
            dedup.append(p)
    return dedup


def _collect_hash_claims(chain_events: Iterable[Dict[str, Any]], root: Path) -> List[Tuple[Path, str]]:
    claims: List[Tuple[Path, str]] = []
    for evt in chain_events:
        hashes = evt.get("hashes")
        if isinstance(hashes, dict):
            for raw_path, raw_hash in hashes.items():
                if not isinstance(raw_path, str) or not isinstance(raw_hash, str):
                    continue
                q = Path(raw_path)
                path = q if q.is_absolute() else (root / q)
                claims.append((path, raw_hash.strip()))
    return claims


def _collect_hash_claims_from_dod(meta_file: Path, root: Path) -> List[Tuple[Path, str]]:
    if not meta_file.exists():
        return []
    claims: List[Tuple[Path, str]] = []
    text = meta_file.read_text(encoding="utf-8")
    dangling_paths: List[Path] = []
    dangling_hashes: List[str] = []
    for line in text.splitlines():
        m_sha = re.search(r"sha256:\s*([0-9a-fA-F]{40,64})", line)
        m_path = re.search(r"(?:path|file):\s*([^\s]+)", line)
        if m_sha and m_path:
            raw_path = m_path.group(1).strip()
            p = Path(raw_path)
            claims.append((p if p.is_absolute() else (root / p), m_sha.group(1)))
            continue
        if m_path:
            raw_path = m_path.group(1).strip()
            p = Path(raw_path)
            dangling_paths.append(p if p.is_absolute() else (root / p))
        if m_sha:
            dangling_hashes.append(m_sha.group(1))

    for i in range(min(len(dangling_paths), len(dangling_hashes))):
        claims.append((dangling_paths[i], dangling_hashes[i]))
    return claims


def check_evidence(phase_id: str, meta_file: Path, activity: Dict[str, Any], paths: Paths) -> Dict[str, Any]:
    missing: List[str] = []
    started = activity.get("events", {}).get("started") or {}
    completed = activity.get("events", {}).get("completed") or {}
    verified = activity.get("events", {}).get("verified") or {}
    chain_events = [e for e in (started, completed, verified) if isinstance(e, dict) and e]

    evidence_paths = _collect_evidence_paths(meta_file, chain_events, paths.root)
    exists_map: Dict[str, bool] = {}
    readable_map: Dict[str, bool] = {}
    for ref in evidence_paths:
        if ref.traversal:
            missing.append(f"evidence.path_traversal:{ref.raw}")
            continue
        p = ref.path
        ok_exists = p.exists()
        ok_read = ok_exists and os.access(p, os.R_OK)
        exists_map[str(p)] = ok_exists
        readable_map[str(p)] = ok_read
        if not ok_exists:
            missing.append(f"evidence.path_missing:{p}")
        elif not ok_read:
            missing.append(f"evidence.path_unreadable:{p}")

    hash_claims = _collect_hash_claims(chain_events, paths.root)
    hash_claims.extend(_collect_hash_claims_from_dod(meta_file, paths.root))
    dedup_hash_claims: List[Tuple[Path, str]] = []
    seen_claims = set()
    for p, claim in hash_claims:
        k = (str(p), claim.lower())
        if k in seen_claims:
            continue
        seen_claims.add(k)
        dedup_hash_claims.append((p, claim))

    hash_results: Dict[str, Dict[str, str]] = {}
    for p, claim in dedup_hash_claims:
        if _has_path_traversal(str(p)):
            missing.append(f"evidence.path_traversal:{p}")
            continue
        key = str(p)
        if not p.exists():
            missing.append(f"evidence.hash_path_missing:{p}")
            continue
        computed = _sha256(p)
        normalized = claim.lower()
        if normalized.startswith("sha256:"):
            expected = normalized.split(":", 1)[1]
        else:
            expected = normalized
        hash_results[key] = {"expected": expected, "actual": computed}
        if computed.lower() != expected.lower():
            missing.append(f"evidence.hash_mismatch:{p}")

    return {
        "paths": [str(p.path) for p in evidence_paths],
        "exists": exists_map,
        "readable": readable_map,
        "hash_checks": hash_results,
        "ok": len(missing) == 0,
        "missing": missing,
    }


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    # Minimal parser for expected phase_status shape only.
    # Supported subset:
    # phases:
    #   PHASE_X:
    #     verdict: PROVEN
    #     requires:
    #       - PHASE_A
    #       - PHASE_B
    data: Dict[str, Any] = {"phases": {}}
    current_phase: Optional[str] = None
    in_requires = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.strip() == "phases:":
            continue
        if re.match(r"^\s{2}[^:\s]+:\s*$", line):
            current_phase = line.strip().rstrip(":")
            data["phases"].setdefault(current_phase, {})
            in_requires = False
            continue
        if current_phase is None:
            continue
        if re.match(r"^\s{4}requires:\s*$", line):
            data["phases"][current_phase]["requires"] = []
            in_requires = True
            continue
        if in_requires and re.match(r"^\s{6}-\s+.+$", line):
            data["phases"][current_phase]["requires"].append(line.strip()[2:].strip())
            continue
        m = re.match(r"^\s{4}(\w+):\s*(.+?)\s*$", line)
        if m:
            k, v = m.group(1), m.group(2)
            data["phases"][current_phase][k] = v
            in_requires = False
    return data


def load_phase_status(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"phases": {}}
    text = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed.setdefault("phases", {})
            if not isinstance(parsed["phases"], dict):
                parsed["phases"] = {}
            return parsed
    except json.JSONDecodeError:
        pass
    parsed = _parse_simple_yaml(text)
    if not isinstance(parsed.get("phases"), dict):
        parsed["phases"] = {}
    return parsed


def _dump_phase_status_yaml(data: Dict[str, Any]) -> str:
    out: List[str] = ["phases:"]
    phases = data.get("phases", {}) if isinstance(data.get("phases"), dict) else {}
    for phase_id in sorted(phases.keys()):
        phase = phases.get(phase_id, {})
        out.append(f"  {phase_id}:")
        verdict = str(phase.get("verdict", "DESIGNED"))
        out.append(f"    verdict: {verdict}")
        requires = phase.get("requires", [])
        if not isinstance(requires, list):
            requires = []
        out.append("    requires:")
        for req in requires:
            out.append(f"      - {req}")
        if "last_verified_ts" in phase:
            out.append(f"    last_verified_ts: {phase['last_verified_ts']}")
        if "commit_sha" in phase:
            out.append(f"    commit_sha: {phase['commit_sha']}")
        if "evidence_path" in phase:
            out.append(f"    evidence_path: {phase['evidence_path']}")
    out.append("")
    return "\n".join(out)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), prefix=f".{path.name}.", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def check_gate(phase_id: str, status_data: Dict[str, Any]) -> Dict[str, Any]:
    phases = status_data.get("phases", {}) if isinstance(status_data.get("phases"), dict) else {}
    phase_entry = phases.get(phase_id, {}) if isinstance(phases.get(phase_id, {}), dict) else {}
    requires = phase_entry.get("requires", [])
    if not isinstance(requires, list):
        requires = []

    missing: List[str] = []
    details: Dict[str, str] = {}
    for req in requires:
        req_entry = phases.get(req, {}) if isinstance(phases.get(req, {}), dict) else {}
        verdict = str(req_entry.get("verdict", "DESIGNED"))
        details[str(req)] = verdict
        if verdict != VERDICT_PROVEN:
            missing.append(f"gate.requires_not_proven:{req}")

    return {
        "requires": [str(x) for x in requires],
        "prereq_verdicts": details,
        "ok": len(missing) == 0,
        "missing": missing,
    }


def evaluate_verdict(meta: Dict[str, str], activity: Dict[str, Any], evidence: Dict[str, Any], gate: Dict[str, Any], commit_ok: bool) -> str:
    has_metadata = bool(meta.get("phase_id") and meta.get("gate") is not None)
    if not commit_ok:
        return VERDICT_PARTIAL

    if (
        has_metadata
        and commit_ok
        and activity.get("chain_valid") is True
        and evidence.get("ok") is True
        and gate.get("ok") is True
    ):
        return VERDICT_PROVEN

    has_started = bool(activity.get("started"))
    has_any_activity = bool(activity.get("started") or activity.get("completed") or activity.get("verified"))
    has_any_problem = bool(evidence.get("missing") or gate.get("missing"))

    if has_any_activity or has_any_problem:
        # If no activity yet, it stays DESIGNED (even if commit is wrong, it's a metadata issue)
        if not has_started:
            return VERDICT_DESIGNED
        return VERDICT_PARTIAL

    if has_metadata:
        if commit_ok:
            return VERDICT_DESIGNED
        else:
            # Metadata present but commit unreachable
            if not has_started:
                return VERDICT_DESIGNED
            return VERDICT_PARTIAL

    return VERDICT_PARTIAL


def run_check(phase_id: str, paths: Paths) -> Dict[str, Any]:
    dod_file = paths.docs_dod / f"DOD__{phase_id}.md"
    meta = parse_dod_metadata(dod_file)

    commit_sha = meta.get("commit_sha", "")
    commit_ok = _git_commit_exists(paths, commit_sha)
    if not commit_ok:
        # mark as evidence requirement for machine readability
        pass

    require_operational = os.environ.get("LUKA_REQUIRE_OPERATIONAL_PROOF", "").strip() == "1"
    strict_parse = require_operational and phase_id == PHASE_OPERATIONAL_TARGET
    enforce_taxonomy = require_operational and phase_id == PHASE_OPERATIONAL_TARGET
    activity = check_activity_events(
        phase_id,
        paths,
        strict_parse=strict_parse,
        enforce_operational_taxonomy=enforce_taxonomy,
    )
    evidence = check_evidence(phase_id, dod_file, activity, paths)
    status_data = load_phase_status(paths.phase_status)
    gate = check_gate(phase_id, status_data)

    verdict = evaluate_verdict(meta, activity, evidence, gate, commit_ok)

    # 1. Synthetic Lock Guard
    synthetic_detected = (phase_id == "PHASE_15_5_3" and activity.get("proof_mode") == PROOF_MODE_SYNTHETIC)

    # 2. Phase Status Protection: Integrity check
    registry_integrity_ok = True
    phase_entry = status_data.get("phases", {}).get(phase_id, {})
    if phase_entry.get("verdict") == VERDICT_PROVEN:
        ev_path_raw = phase_entry.get("evidence_path")
        if ev_path_raw:
            ev_path = Path(ev_path_raw)
            if not ev_path.is_absolute():
                ev_path = paths.root / ev_path
            if not ev_path.exists():
                registry_integrity_ok = False
        else:
            registry_integrity_ok = False

    if not registry_integrity_ok:
        verdict = VERDICT_PARTIAL
    
    # 4. Blueprint Alignment Check (preflight)
    blueprint_mismatch = (BLUEPRINT_REV != "Rev1.3")

    missing: List[str] = []
    if not registry_integrity_ok:
        missing.append("registry.verdict_without_artifact")
    if blueprint_mismatch:
        missing.append("governance.blueprint_schema_mismatch")
    missing.extend(activity.get("missing", []))
    taxonomy_missing = activity.get("taxonomy_missing", [])
    missing.extend(evidence.get("missing", []))
    missing.extend(gate.get("missing", []))
    if not commit_ok:
        missing.append("metadata.commit_sha_unreachable")

    if require_operational and phase_id == PHASE_OPERATIONAL_TARGET:
        if activity.get("proof_mode") != PROOF_MODE_OPERATIONAL:
            missing.append("proof.synthetic_not_allowed")
        if taxonomy_missing:
            missing.append("taxonomy.incomplete_event")
        if "proof.synthetic_not_allowed" in missing or "taxonomy.incomplete_event" in missing:
            verdict = VERDICT_PARTIAL

    return {
        "phase_id": phase_id,
        "verdict": verdict,
        "meta": {
            **meta,
            "dod_file": str(dod_file),
            "commit_sha_reachable": commit_ok,
        },
        "checks": {
            "activity_chain": {
                "started": activity.get("started"),
                "completed": activity.get("completed"),
                "verified": activity.get("verified"),
                "order_ok": activity.get("order_ok"),
                "latest_order_ok": activity.get("latest_order_ok"),
                "event_count": activity.get("event_count"),
                "proof_mode": activity.get("proof_mode"),
                "taxonomy_ok": activity.get("taxonomy_ok", False),
                "taxonomy_missing": sorted(set(taxonomy_missing)),
            },
            "evidence": evidence,
            "gate": gate,
            "synthetic_detected": synthetic_detected,
            "registry_integrity_ok": registry_integrity_ok,
            "blueprint_mismatch": blueprint_mismatch,
        },
        "missing": sorted(set(missing)),
    }


def write_report(paths: Paths, phase_results: List[Dict[str, Any]]) -> Path:
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = paths.reports_dir / f"{ts}_dod.json"
    head = ""
    try:
        head = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(paths.root), text=True)
            .strip()
        )
    except Exception:
        head = ""

    payload = {
        "schema_version": "dod_report_v2",
        "ts": _utc_now(),
        "git_head": head,
        "blueprint_key": BLUEPRINT_KEY,
        "blueprint_rev": BLUEPRINT_REV,
        "phases": {r["phase_id"]: r for r in phase_results},
    }
    _atomic_write(report_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    latest = paths.reports_dir / "dod_report.latest.json"
    _atomic_write(latest, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return report_path


def update_phase_status(paths: Paths, phase_results: List[Dict[str, Any]], report_path: Path) -> None:
    status = load_phase_status(paths.phase_status)
    phases = status.setdefault("phases", {})
    if not isinstance(phases, dict):
        phases = {}
        status["phases"] = phases

    for res in phase_results:
        phase_id = res["phase_id"]
        entry = phases.get(phase_id, {}) if isinstance(phases.get(phase_id, {}), dict) else {}
        entry["verdict"] = res["verdict"]
        if res["verdict"] == VERDICT_PROVEN:
            entry["last_verified_ts"] = _utc_now()
        commit_sha = str(res.get("meta", {}).get("commit_sha", "")).strip()
        if commit_sha:
            entry["commit_sha"] = commit_sha
        entry["evidence_path"] = str(report_path)
        # preserve requires if already present
        if not isinstance(entry.get("requires"), list):
            entry["requires"] = []
        phases[phase_id] = entry

    _atomic_write(paths.phase_status, _dump_phase_status_yaml(status))


def collect_phase_ids(paths: Paths, specific_phase: Optional[str], run_all: bool) -> List[str]:
    if specific_phase:
        return [specific_phase]
    if not run_all:
        return []
    files = sorted(glob.glob(str(paths.docs_dod / "DOD__*.md")))
    out: List[str] = []
    for path in files:
        pid = Path(path).name.replace("DOD__", "").replace(".md", "")
        out.append(pid)
    return out


def compute_exit_code(results: List[Dict[str, Any]]) -> int:
    verdicts = [r.get("verdict") for r in results]
    if any(v == VERDICT_DESIGNED for v in verdicts):
        return 3
    if any(v == VERDICT_PARTIAL for v in verdicts):
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DoD Auto-Checker (Phase 2 proof engine)")
    parser.add_argument("--phase", help="Check specific Phase ID")
    parser.add_argument("--all", action="store_true", help="Check all DOD__*.md")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--missing-only", action="store_true", help="Only print phases with missing items")
    parser.add_argument("--update-status", action="store_true", help="Update core/governance/phase_status.yaml atomically")
    args = parser.parse_args()

    try:
        paths = resolve_paths()
        phase_ids = collect_phase_ids(paths, args.phase, args.all)
        if not phase_ids:
            parser.print_help()
            return 4

        results = [run_check(pid, paths) for pid in phase_ids]
        report_path = write_report(paths, results)

        if args.update_status:
            update_phase_status(paths, results, report_path)

        output_results = results
        if args.missing_only:
            output_results = [r for r in results if r.get("missing")]

        if args.json:
            print(json.dumps({"report_path": str(report_path), "results": output_results}, ensure_ascii=False, indent=2))
        else:
            print(f"DoD Report: {report_path}")
            print(f"{'PHASE':<24} {'VERDICT':<10} MISSING")
            for r in output_results:
                m = ",".join(r.get("missing", []))
                print(f"{r['phase_id']:<24} {r['verdict']:<10} {m}")

        return compute_exit_code(results)
    except Exception as exc:
        print(f"dod_checker_internal_error:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
