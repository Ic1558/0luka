from __future__ import annotations

import json

import pytest

from core.execution.execution_envelope import (
    EvidenceInfo,
    ExecutionEnvelope,
    ExecutorInfo,
    PolicyInfo,
    ProvenanceInfo,
    ResultInfo,
    RoutingInfo,
    SealInfo,
    TimestampInfo,
    WrapperInfo,
)


def _build_envelope() -> ExecutionEnvelope:
    return ExecutionEnvelope.build(
        execution_id="exec-001",
        task_id="task-001",
        trace_id="task-001",
        intent={"lane": "lisa"},
        command={"command": "ls -la"},
        accepted_input={
            "schema_version": "clec.v1",
            "task": {"task_id": "task-001"},
        },
        routing=RoutingInfo(router="core/router.py", route="canonical_lisa", policy_version="p1"),
        executor=ExecutorInfo(executor_id="system/agents/lisa_executor.py", executor_version="v1"),
        policy=PolicyInfo(policy_id="phase1c", policy_version="p1"),
        wrapper=WrapperInfo(wrapper_name="wrapper.sh", wrapper_version="v1"),
        timestamps=TimestampInfo(created_at="t0", started_at="t1", finished_at="t2"),
        provenance=ProvenanceInfo(inputs_sha256="00", outputs_sha256="11", envelope_sha256=""),
        evidence=EvidenceInfo(
            commands=["ls -la"],
            logs=[],
            execution_events=[{"event": "execution_started"}, {"event": "execution_finished"}],
        ),
        result=ResultInfo(status="ok", summary="completed"),
        seal=SealInfo(),
    )


def test_execution_envelope_supports_structured_subobjects_and_serialization() -> None:
    envelope = _build_envelope()
    data = envelope.to_dict()

    assert data["routing"] == {
        "router": "core/router.py",
        "route": "canonical_lisa",
        "policy_version": "p1",
    }
    assert data["executor"] == {
        "executor_id": "system/agents/lisa_executor.py",
        "executor_version": "v1",
    }
    assert data["evidence"]["execution_events"][0]["event"] == "execution_started"


def test_builder_accepts_plain_dict_inputs_and_normalizes_subobjects() -> None:
    envelope = ExecutionEnvelope.build(
        execution_id="exec-001",
        task_id="task-001",
        trace_id="task-001",
        intent={"lane": "lisa"},
        accepted_input={"schema_version": "clec.v1", "task": {"task_id": "task-001"}},
        routing={"router": "core/router.py", "route": "canonical_lisa", "policy_version": "p1"},
        executor={"executor_id": "system/agents/lisa_executor.py", "executor_version": "v1"},
        policy={"policy_id": "phase1c", "policy_version": "p1"},
        wrapper={"wrapper_name": "wrapper.sh", "wrapper_version": "v1"},
        timestamps={"created_at": "t0", "started_at": "t1", "finished_at": "t2"},
        evidence={
            "commands": ["ls -la"],
            "logs": [],
            "execution_events": [{"event": "execution_started"}],
        },
        result={"status": "ok", "summary": "completed"},
        provenance={"inputs_sha256": "00", "outputs_sha256": "11", "envelope_sha256": ""},
    )

    assert isinstance(envelope.routing, RoutingInfo)
    assert isinstance(envelope.executor, ExecutorInfo)
    assert envelope.evidence.execution_events == [{"event": "execution_started"}]


def test_builder_accepts_structured_dataclasses_and_safe_defaults() -> None:
    envelope = ExecutionEnvelope.build(
        execution_id="exec-002",
        task_id="task-002",
        trace_id="trace-002",
        intent={"lane": "lisa"},
        accepted_input={"schema_version": "clec.v1", "task": {"task_id": "task-002"}},
        routing=RoutingInfo(router="core/router.py", route="canonical_lisa", policy_version="p1"),
        executor=ExecutorInfo(executor_id="system/agents/lisa_executor.py", executor_version="v1"),
        policy=PolicyInfo(policy_id="phase1c", policy_version="p1"),
        wrapper=WrapperInfo(wrapper_name="wrapper.sh", wrapper_version="v1"),
        timestamps=TimestampInfo(created_at="t0", started_at="", finished_at=""),
    )

    assert envelope.v == "0luka.execution_envelope/v1"
    assert envelope.evidence.commands == []
    assert envelope.evidence.logs == []
    assert envelope.evidence.execution_events == []
    assert envelope.result.status == ""
    assert envelope.result.summary == ""
    assert envelope.provenance.inputs_sha256 == ""
    assert envelope.provenance.outputs_sha256 == ""
    assert envelope.provenance.envelope_sha256 == ""
    assert envelope.seal.alg == ""
    assert envelope.seal.value == ""


def test_execution_envelope_seal_is_deterministic_and_immutable() -> None:
    envelope = _build_envelope()
    sealed = envelope.sealed()
    assert sealed is not envelope
    assert envelope.provenance.envelope_sha256 == ""
    assert sealed.seal.alg == "sha256"

    # sealing again produces same seal because canonical inputs are immutable
    assert sealed.sealed().seal == sealed.seal
    assert sealed.provenance.envelope_sha256
    payload = json.loads(sealed.to_json())
    assert payload["seal"]["value"] == sealed.seal.value


def test_execution_events_survive_serialization() -> None:
    envelope = _build_envelope()
    env = envelope.sealed()
    data = json.loads(env.to_json())
    assert "execution_events" in data["evidence"]
    assert data["evidence"]["execution_events"][1]["event"] == "execution_finished"


def test_serialization_is_deterministic_and_hash_is_compatible() -> None:
    envelope = _build_envelope()
    dict_backed = ExecutionEnvelope.build(
        execution_id="exec-001",
        task_id="task-001",
        trace_id="task-001",
        intent={"lane": "lisa"},
        command={"command": "ls -la"},
        accepted_input={
            "schema_version": "clec.v1",
            "task": {"task_id": "task-001"},
        },
        routing={"router": "core/router.py", "route": "canonical_lisa", "policy_version": "p1"},
        executor={"executor_id": "system/agents/lisa_executor.py", "executor_version": "v1"},
        policy={"policy_id": "phase1c", "policy_version": "p1"},
        wrapper={"wrapper_name": "wrapper.sh", "wrapper_version": "v1"},
        timestamps={"created_at": "t0", "started_at": "t1", "finished_at": "t2"},
        provenance={"inputs_sha256": "00", "outputs_sha256": "11", "envelope_sha256": ""},
        evidence={
            "commands": ["ls -la"],
            "logs": [],
            "execution_events": [{"event": "execution_started"}, {"event": "execution_finished"}],
        },
        result={"status": "ok", "summary": "completed"},
        seal={},
    )

    assert envelope.to_json() == dict_backed.to_json()
    assert envelope.envelope_hash() == dict_backed.envelope_hash()

    data = json.loads(envelope.sealed().to_json())
    assert data["v"] == "0luka.execution_envelope/v1"
    assert data["trace_id"] == "task-001"
    assert "accepted_input" in data
    assert "routing" in data


def test_validate_rejects_missing_required_fields_and_bad_seal() -> None:
    with pytest.raises(ValueError, match="v is required"):
        ExecutionEnvelope.build(
            v="",
            execution_id="exec-001",
            task_id="task-001",
            trace_id="trace-001",
            intent={"lane": "lisa"},
            accepted_input={"schema_version": "clec.v1", "task": {"task_id": "task-001"}},
            routing={"router": "core/router.py", "route": "canonical_lisa", "policy_version": "p1"},
            executor={"executor_id": "system/agents/lisa_executor.py", "executor_version": "v1"},
            policy={"policy_id": "phase1c", "policy_version": "p1"},
            wrapper={"wrapper_name": "wrapper.sh", "wrapper_version": "v1"},
            timestamps={"created_at": "t0", "started_at": "t1", "finished_at": "t2"},
        )

    with pytest.raises(ValueError, match="seal must include both alg and value"):
        ExecutionEnvelope.build(
            execution_id="exec-001",
            task_id="task-001",
            trace_id="trace-001",
            intent={"lane": "lisa"},
            accepted_input={"schema_version": "clec.v1", "task": {"task_id": "task-001"}},
            routing={"router": "core/router.py", "route": "canonical_lisa", "policy_version": "p1"},
            executor={"executor_id": "system/agents/lisa_executor.py", "executor_version": "v1"},
            policy={"policy_id": "phase1c", "policy_version": "p1"},
            wrapper={"wrapper_name": "wrapper.sh", "wrapper_version": "v1"},
            timestamps={"created_at": "t0", "started_at": "t1", "finished_at": "t2"},
            seal={"alg": "sha256", "value": ""},
        )
