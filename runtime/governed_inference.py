"""AG-70: Governed Inference Fabric — governed routing of inference requests."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def route_inference(
    prompt: str,
    preferred_provider: str | None = None,
    operator_id: str = "system",
    routing_hint: str = "cost",
) -> dict:
    """Route an inference request through the governed fabric.

    In this implementation the fabric is provider-agnostic and records the
    routing decision without calling an external API. Actual provider
    invocation is delegated to the operator's chosen provider integration.
    """
    from runtime.governed_inference_policy import PROVIDERS, DEFAULT_PROVIDER, INFERENCE_VERSION

    provider = preferred_provider if preferred_provider in PROVIDERS else DEFAULT_PROVIDER

    request_id = str(uuid.uuid4())
    record = {
        "request_id": request_id,
        "operator_id": operator_id,
        "provider": provider,
        "routing_hint": routing_hint,
        "prompt_len": len(prompt),
        "governed": True,
        "version": INFERENCE_VERSION,
        "response": None,  # populated by actual provider call outside this layer
        "ts_routed": _now(),
    }

    sd = _state_dir()
    _atomic_write(sd / "runtime_governed_inference_latest.json", record)
    _append_jsonl(sd / "runtime_governed_inference_log.jsonl", record)

    idx_path = sd / "runtime_governed_inference_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"request_id": request_id, "provider": provider, "ts_routed": record["ts_routed"]})
    _atomic_write(idx_path, idx)

    return record


def get_inference_latest() -> dict | None:
    sd = _state_dir()
    p = sd / "runtime_governed_inference_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def list_inference_requests() -> list:
    sd = _state_dir()
    p = sd / "runtime_governed_inference_index.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []
