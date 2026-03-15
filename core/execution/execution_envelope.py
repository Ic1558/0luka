from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _to_dict(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return value


@dataclass(frozen=True)
class RoutingInfo:
    router: str = ""
    route: str = ""
    policy_version: str = ""


@dataclass(frozen=True)
class ExecutorInfo:
    executor_id: str = ""
    executor_version: str = ""


@dataclass(frozen=True)
class PolicyInfo:
    policy_id: str = ""
    policy_version: str = ""


@dataclass(frozen=True)
class WrapperInfo:
    wrapper_name: str = ""
    wrapper_version: str = ""


@dataclass(frozen=True)
class TimestampInfo:
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""


@dataclass(frozen=True)
class EvidenceInfo:
    commands: List[Any] = field(default_factory=list)
    logs: List[Any] = field(default_factory=list)
    execution_events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ResultInfo:
    status: str = ""
    summary: str = ""


@dataclass(frozen=True)
class ProvenanceInfo:
    inputs_sha256: str = ""
    outputs_sha256: str = ""
    envelope_sha256: str = ""


@dataclass(frozen=True)
class SealInfo:
    alg: str = ""
    value: str = ""


def _normalize_dataclass_input(value: Any, cls: type[Any], default: Dict[str, Any] | None = None) -> Any:
    data = dict(default or {})
    if value is not None:
        data.update(_normalize_mapping(value))
    return cls(**data)


def _normalize_mapping(value: Any) -> Dict[str, Any]:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Expected mapping-compatible value, got {type(value)!r}")


def _normalize_execution_events(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    events: List[Dict[str, Any]] = []
    for event in value:
        if not isinstance(event, Mapping):
            raise TypeError("execution_events must contain mapping items")
        events.append(dict(event))
    return events


@dataclass(frozen=True)
class ExecutionEnvelope:
    v: str
    envelope_version: str
    execution_id: str
    task_id: str
    trace_id: str

    intent: Dict[str, Any]
    command: Dict[str, Any]
    accepted_input: Dict[str, Any]
    routing: RoutingInfo
    executor: ExecutorInfo
    policy: PolicyInfo
    wrapper: WrapperInfo

    timestamps: TimestampInfo
    provenance: ProvenanceInfo
    evidence: EvidenceInfo
    result: ResultInfo

    seal: SealInfo = field(default_factory=SealInfo, compare=False)

    @classmethod
    def build(
        cls,
        *,
        execution_id: str,
        task_id: str,
        trace_id: str,
        intent: Dict[str, Any],
        accepted_input: Dict[str, Any],
        routing: RoutingInfo | Dict[str, Any],
        executor: ExecutorInfo | Dict[str, Any],
        policy: PolicyInfo | Dict[str, Any],
        wrapper: WrapperInfo | Dict[str, Any],
        timestamps: TimestampInfo | Dict[str, Any],
        evidence: EvidenceInfo | Dict[str, Any] | None = None,
        result: ResultInfo | Dict[str, Any] | None = None,
        provenance: ProvenanceInfo | Dict[str, Any] | None = None,
        seal: SealInfo | Dict[str, Any] | None = None,
        v: str = "0luka.execution_envelope/v1",
        envelope_version: str = "v1",
        command: Dict[str, Any] | None = None,
    ) -> "ExecutionEnvelope":
        envelope = cls(
            v=v,
            envelope_version=envelope_version,
            execution_id=execution_id,
            task_id=task_id,
            trace_id=trace_id,
            intent=dict(intent),
            command=dict(command or {}),
            accepted_input=dict(accepted_input),
            routing=_normalize_dataclass_input(routing, RoutingInfo),
            executor=_normalize_dataclass_input(executor, ExecutorInfo),
            policy=_normalize_dataclass_input(policy, PolicyInfo),
            wrapper=_normalize_dataclass_input(wrapper, WrapperInfo),
            timestamps=_normalize_dataclass_input(timestamps, TimestampInfo),
            evidence=_normalize_dataclass_input(
                evidence,
                EvidenceInfo,
                default={"commands": [], "logs": [], "execution_events": []},
            ),
            result=_normalize_dataclass_input(
                result,
                ResultInfo,
                default={"status": "", "summary": ""},
            ),
            provenance=_normalize_dataclass_input(
                provenance,
                ProvenanceInfo,
                default={"inputs_sha256": "", "outputs_sha256": "", "envelope_sha256": ""},
            ),
            seal=_normalize_dataclass_input(seal, SealInfo, default={"alg": "", "value": ""}),
        )
        envelope.validate()
        return envelope

    def __post_init__(self) -> None:
        object.__setattr__(self, "routing", RoutingInfo(**_normalize_mapping(self.routing)))
        object.__setattr__(self, "executor", ExecutorInfo(**_normalize_mapping(self.executor)))
        object.__setattr__(self, "policy", PolicyInfo(**_normalize_mapping(self.policy)))
        object.__setattr__(self, "wrapper", WrapperInfo(**_normalize_mapping(self.wrapper)))
        object.__setattr__(self, "timestamps", TimestampInfo(**_normalize_mapping(self.timestamps)))
        object.__setattr__(self, "provenance", ProvenanceInfo(**_normalize_mapping(self.provenance)))
        evidence = _normalize_mapping(self.evidence)
        evidence["execution_events"] = _normalize_execution_events(evidence.get("execution_events", []))
        object.__setattr__(self, "evidence", EvidenceInfo(**evidence))
        object.__setattr__(self, "result", ResultInfo(**_normalize_mapping(self.result)))
        seal_mapping = _normalize_mapping(self.seal) if self.seal else {}
        object.__setattr__(self, "seal", SealInfo(**seal_mapping))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "v": self.v,
            "envelope_version": self.envelope_version,
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "intent": self.intent,
            "command": self.command,
            "accepted_input": self.accepted_input,
            "routing": _to_dict(self.routing),
            "executor": _to_dict(self.executor),
            "policy": _to_dict(self.policy),
            "wrapper": _to_dict(self.wrapper),
            "timestamps": _to_dict(self.timestamps),
            "provenance": _to_dict(self.provenance),
            "evidence": _to_dict(self.evidence),
            "result": _to_dict(self.result),
            "seal": _to_dict(self.seal),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def validate(self) -> None:
        if not self.v:
            raise ValueError("v is required")
        if not self.execution_id:
            raise ValueError("execution_id is required")
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.trace_id:
            raise ValueError("trace_id is required")
        if self.seal and ((self.seal.alg and not self.seal.value) or (self.seal.value and not self.seal.alg)):
            raise ValueError("seal must include both alg and value")

    def envelope_hash(self) -> str:
        data = self.to_dict()
        data["seal"] = {}
        data["provenance"] = {**data["provenance"], "envelope_sha256": ""}
        return hashlib.sha256(_canonical_json(data)).hexdigest()

    def sealed(self) -> "ExecutionEnvelope":
        self.validate()
        envelope_hash = self.envelope_hash()
        provenance = {**_to_dict(self.provenance), "envelope_sha256": envelope_hash}
        seal_value = hashlib.sha256(envelope_hash.encode("utf-8")).hexdigest()
        seal = {"alg": "sha256", "value": seal_value}
        return dataclasses.replace(self, provenance=provenance, seal=seal)
