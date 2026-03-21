#!/usr/bin/env python3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.verify.test_phase15_runtime_boundary_audit_ambiguous_domain import (
    test_runtime_boundary_audit_ambiguous_runtime_evidence_fails_closed,
)
from core.verify.test_phase15_runtime_boundary_audit_clean_domain import (
    test_runtime_boundary_audit_clean_runtime_evidence_yields_zero_findings,
)
from core.verify.test_phase15_runtime_boundary_audit_minimal_domain import (
    test_runtime_boundary_audit_detects_machine_specific_path_read_only,
)
from core.verify.test_phase15_runtime_boundary_audit_missing_domain import (
    test_runtime_boundary_audit_missing_runtime_evidence_fails_closed,
)


def test_runtime_boundary_audit_proofset_consolidated_lane() -> None:
    test_runtime_boundary_audit_detects_machine_specific_path_read_only()
    test_runtime_boundary_audit_clean_runtime_evidence_yields_zero_findings()
    test_runtime_boundary_audit_missing_runtime_evidence_fails_closed()
    test_runtime_boundary_audit_ambiguous_runtime_evidence_fails_closed()


if __name__ == "__main__":
    test_runtime_boundary_audit_proofset_consolidated_lane()
    print("test_phase15_runtime_boundary_audit_proofset_consolidation: all ok")
