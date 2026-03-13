"""Schema tests for Antigravity state writeback scaffolding."""

from __future__ import annotations

import unittest

from runtime.antigravity.runtime_state.antigravity_runtime_state import (
    AntigravityRuntimeState,
    ApprovalState,
    RuntimePhase,
)
from runtime.antigravity.runtime_state.state_writeback import (
    AntigravityStateWriteback,
    StateWritebackRequest,
)


class StateWritebackSchemaTests(unittest.TestCase):
    """Validate scaffold-only writeback contract behavior."""

    def setUp(self) -> None:
        self.state = AntigravityRuntimeState(
            phase=RuntimePhase.VERIFIED,
            approval_state=ApprovalState.APPROVED_WITH_CONDITIONS,
            blockers=["b1", "b2"],
            evidence_refs=["e1"],
            working_directory="/tmp/workdir",
            canonical_entrypoint="runtime/services/antigravity_realtime/runner.zsh",
        )
        self.writeback = AntigravityStateWriteback()

    def test_validate_request_always_denies(self) -> None:
        request = StateWritebackRequest(
            state=self.state,
            target_path="runtime/antigravity/state/runtime_state.json",
        )

        result = self.writeback.validate_request(request)

        self.assertFalse(result.allowed)
        self.assertEqual(result.target_path, request.target_path)
        self.assertIn("not implemented", result.reason)
        self.assertIn("approved implementation PR", result.reason)

    def test_preview_payload_returns_allowed_fields_only(self) -> None:
        payload = self.writeback.preview_payload(self.state)

        self.assertEqual(
            set(payload.keys()),
            {
                "phase",
                "approval_state",
                "blockers",
                "evidence_refs",
                "working_directory",
                "canonical_entrypoint",
            },
        )

    def test_preview_payload_excludes_unexpected_and_sensitive_fields(self) -> None:
        payload = self.writeback.preview_payload(self.state)

        self.assertNotIn("secrets", payload)
        self.assertNotIn("broker_auth", payload)
        self.assertNotIn("runtime_mutation", payload)
        self.assertNotIn("target_path", payload)
        self.assertNotIn("write_mode", payload)
        self.assertNotIn("allowed", payload)

    def test_preview_payload_serializes_enums_to_strings(self) -> None:
        payload = self.writeback.preview_payload(self.state)

        self.assertEqual(payload["phase"], RuntimePhase.VERIFIED.value)
        self.assertEqual(
            payload["approval_state"], ApprovalState.APPROVED_WITH_CONDITIONS.value
        )
        self.assertIsInstance(payload["phase"], str)
        self.assertIsInstance(payload["approval_state"], str)

    def test_preview_payload_keeps_lists_as_plain_lists(self) -> None:
        payload = self.writeback.preview_payload(self.state)

        self.assertEqual(payload["blockers"], ["b1", "b2"])
        self.assertEqual(payload["evidence_refs"], ["e1"])
        self.assertIsInstance(payload["blockers"], list)
        self.assertIsInstance(payload["evidence_refs"], list)


if __name__ == "__main__":
    unittest.main()
