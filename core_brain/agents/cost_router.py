from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

RISK_TO_TIER = {
    "R3": "T0",
    "R2": "T0",
    "R1": "T2",
    "R0": "T3",
}

COMPLEXITY_TO_TIER = {
    "L3_plus": "T0",
    "L2": "T1",
    "L1": "T2",
    "L0": "T3",
}

TIER_STRICTNESS = {
    "T0": 4,
    "T1": 3,
    "T2": 2,
    "T3": 1,
    "T4": 0,
}

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_REGISTRY_REL = Path("core_brain/agents/model_registry.yaml")
AGENT_CONFIG_REL = Path("core_brain/agents/agent_config.yaml")
DECISIONS_LOG_REL = Path("observability/reports/cost_router/decisions.jsonl")


def _resolve_path(env_key: str, default_rel: Path) -> Path:
    raw = os.environ.get(env_key, "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_absolute() else (REPO_ROOT / p)
    return REPO_ROOT / default_rel


def _read_json_yaml(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise RuntimeError(f"config_read_failure:{path}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_yaml_or_json:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_mapping:{path}")
    return payload


def load_model_registry() -> Dict[str, Any]:
    path = _resolve_path("COST_ROUTER_MODEL_REGISTRY_PATH", MODEL_REGISTRY_REL)
    registry = _read_json_yaml(path)
    tiers = registry.get("tiers")
    if not isinstance(tiers, dict):
        raise ValueError("invalid_model_registry:tiers")
    return registry


def load_agent_config() -> Dict[str, Any]:
    path = _resolve_path("COST_ROUTER_AGENT_CONFIG_PATH", AGENT_CONFIG_REL)
    return _read_json_yaml(path)


def _normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./")


def _iter_task_paths(task: Dict[str, Any]) -> Iterable[str]:
    path_keys = ("path", "file", "target", "source_path")
    list_keys = ("paths", "files", "modifies")
    for key in path_keys:
        value = task.get(key)
        if isinstance(value, str) and value.strip():
            yield _normalize_path(value)
    for key in list_keys:
        value = task.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    yield _normalize_path(item)
        elif isinstance(value, str) and value.strip():
            yield _normalize_path(value)
    text_blobs = []
    for key in ("intent", "description", "summary"):
        value = task.get(key)
        if isinstance(value, str):
            text_blobs.append(value)
    for text in text_blobs:
        for token in text.split():
            token = token.strip()
            if token.startswith("modifies:"):
                yield _normalize_path(token.split(":", 1)[1])


def classify_risk(task: Dict[str, Any]) -> str:
    paths = list(_iter_task_paths(task))
    if not paths:
        return "R0"
    for p in paths:
        if p.startswith("core/"):
            return "R3"
    for p in paths:
        if p.startswith("tools/") or p.startswith(".github/"):
            return "R2"
    for p in paths:
        if p.startswith("modules/") or p.startswith("docs/") or p.startswith("core_brain/"):
            return "R1"
    return "R0"


def classify_complexity(task: Dict[str, Any]) -> str:
    raw = task.get("complexity")
    if isinstance(raw, int):
        if raw >= 3:
            return "L3_plus"
        if raw == 2:
            return "L2"
        if raw == 1:
            return "L1"
        return "L0"
    if isinstance(raw, str) and raw.strip():
        n = raw.strip().lower()
        if n in {"l3", "l3+", "l3_plus", "3", "high"}:
            return "L3_plus"
        if n in {"l2", "2", "medium"}:
            return "L2"
        if n in {"l1", "1", "low"}:
            return "L1"
        if n in {"l0", "0", "trivial"}:
            return "L0"

    intent = str(task.get("intent", "")).lower()
    if any(k in intent for k in ("refactor", "rewrite", "migration", "architecture")):
        return "L3_plus"
    if any(k in intent for k in ("implement", "feature", "integration")):
        return "L2"
    if any(k in intent for k in ("fix", "bug", "patch")):
        return "L1"
    if any(k in intent for k in ("typo", "format", "docs", "rename")):
        return "L0"
    return "L1"


def has_governance_impact(task: Dict[str, Any]) -> bool:
    for p in _iter_task_paths(task):
        if p.startswith("core/governance/") or p.startswith("core_brain/governance/"):
            return True
    return False


def _compose_tier(risk_tier: str, complexity_tier: str) -> str:
    risk_score = TIER_STRICTNESS.get(risk_tier, 0)
    complexity_score = TIER_STRICTNESS.get(complexity_tier, 0)
    return risk_tier if risk_score >= complexity_score else complexity_tier


def _pick_model(registry: Dict[str, Any], tier: str) -> str:
    tiers = registry.get("tiers", {})
    tier_cfg = tiers.get(tier, {})
    models = tier_cfg.get("models", [])
    if not isinstance(models, list) or not models:
        raise ValueError(f"no_models_in_tier:{tier}")
    return str(models[0])


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError as exc:
        raise RuntimeError(f"decision_log_write_failed:{path}") from exc


def select_model(task: Dict[str, Any]) -> Dict[str, Any]:
    registry = load_model_registry()
    risk_level = classify_risk(task)
    complexity_level = classify_complexity(task)
    risk_tier = RISK_TO_TIER[risk_level]
    complexity_tier = COMPLEXITY_TO_TIER[complexity_level]
    governance_impact = has_governance_impact(task)
    tier_selected = "T0" if governance_impact else _compose_tier(risk_tier, complexity_tier)
    model = _pick_model(registry, tier_selected)

    ts = datetime.now(timezone.utc)
    decision = {
        "ts_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ts_epoch_ms": int(ts.timestamp() * 1000),
        "task_id": str(task.get("task_id", "")),
        "tier_selected": tier_selected,
        "selected_model": model,
        "risk_level": risk_level,
        "complexity_level": complexity_level,
        "governance_impact": governance_impact,
        "reason": f"risk={risk_level},complexity={complexity_level}",
        "requires_approval": tier_selected in {"T0", "T1"},
        "classifier_chain": f"risk={risk_tier},complexity={complexity_tier},gov={'T0' if governance_impact else 'none'}",
    }
    decisions_path = _resolve_path("COST_ROUTER_DECISIONS_PATH", DECISIONS_LOG_REL)
    _append_jsonl(decisions_path, decision)
    return decision
