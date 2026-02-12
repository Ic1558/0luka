#!/usr/bin/env python3
"""
Tests for Auto-Adaptive Governor Router

Black-box CLI tests covering:
- core/ => HARD mode
- core_brain/ => MED mode
- docs/ => SOFT mode
- unknown path => exit 4
- forbidden patterns => exit 4
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestGovernorRouter:
    """Test suite for auto_governor_router.py CLI."""
    
    ROUTER_PATH = "tools/ops/auto_governor_router.py"
    
    def run_router(self, *args):
        """Run router CLI and return (stdout, stderr, exit_code)."""
        cmd = [sys.executable, self.ROUTER_PATH] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent  # Repo root
        )
        return result.stdout, result.stderr, result.returncode
    
    def run_router_json(self, *args):
        """Run router with --json and return parsed JSON + exit code."""
        stdout, stderr, exit_code = self.run_router(*args, "--json")
        if stdout.strip():
            try:
                data = json.loads(stdout)
                return data, exit_code
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON output: {stdout}\nStderr: {stderr}")
        else:
            pytest.fail(f"No JSON output. Stderr: {stderr}")
    
    # ===== Ring Classification Tests =====
    
    def test_core_governance_is_hard_mode(self):
        """core/governance/ should trigger HARD mode (R3 ring)."""
        data, exit_code = self.run_router_json(
            "--nl", "edit core/governance/agents.md"
        )
        
        assert data['mode'] == 'HARD', f"Expected HARD mode, got {data['mode']}"
        assert data['ring'] == 'R3', f"Expected R3 ring, got {data['ring']}"
        assert data['risk'] == 'Critical', f"Expected Critical risk, got {data['risk']}"
        assert exit_code == 0, f"Expected exit 0, got {exit_code}"
    
    def test_core_path_is_hard_mode(self):
        """core/ should trigger HARD mode (R3 ring)."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "core/verify/test_something.py"
        )
        
        assert data['mode'] == 'HARD'
        assert data['ring'] == 'R3'
        assert data['risk'] == 'Critical'
        assert exit_code == 0
    
    def test_github_workflows_is_hard_mode(self):
        """.github/workflows/ should trigger HARD mode (R3 ring)."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", ".github/workflows/ci.yml"
        )
        
        assert data['mode'] == 'HARD'
        assert data['ring'] == 'R3'
        assert exit_code == 0
    
    def test_core_brain_is_med_mode(self):
        """core_brain/ should trigger MED mode (R2 ring)."""
        data, exit_code = self.run_router_json(
            "--nl", "update core_brain/governance/agents.md"
        )
        
        assert data['mode'] == 'MED', f"Expected MED mode, got {data['mode']}"
        assert data['ring'] == 'R2', f"Expected R2 ring, got {data['ring']}"
        assert data['risk'] == 'High', f"Expected High risk, got {data['risk']}"
        assert exit_code == 0
    
    def test_tools_ops_is_med_mode(self):
        """tools/ops/ should trigger MED mode (R2 ring)."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "tools/ops/some_script.py"
        )
        
        assert data['mode'] == 'MED'
        assert data['ring'] == 'R2'
        assert exit_code == 0
    
    def test_modules_is_med_mode(self):
        """modules/ should trigger MED mode (R1 ring)."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "modules/phase1/test.py"
        )
        
        assert data['mode'] == 'MED'
        assert data['ring'] == 'R1'
        assert data['risk'] == 'Medium'
        assert exit_code == 0
    
    def test_docs_is_soft_mode(self):
        """docs/ should trigger SOFT mode (R0 ring)."""
        data, exit_code = self.run_router_json(
            "--nl", "fix typo in docs/readme.md"
        )
        
        assert data['mode'] == 'SOFT', f"Expected SOFT mode, got {data['mode']}"
        assert data['ring'] == 'R0', f"Expected R0 ring, got {data['ring']}"
        assert data['risk'] == 'Low', f"Expected Low risk, got {data['risk']}"
        assert exit_code == 0
    
    def test_reports_is_soft_mode(self):
        """reports/ should trigger SOFT mode (R0 ring)."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "reports/summary/latest.md"
        )
        
        assert data['mode'] == 'SOFT'
        assert data['ring'] == 'R0'
        assert exit_code == 0
    
    def test_observability_is_soft_mode(self):
        """observability/ should trigger SOFT mode (R0 ring)."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "observability/telemetry/status.json"
        )
        
        assert data['mode'] == 'SOFT'
        assert data['ring'] == 'R0'
        assert exit_code == 0
    
    # ===== Unknown Scope Tests =====
    
    def test_unknown_path_exits_4(self):
        """Unknown paths should exit with code 4."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "/unknown/random/path.txt"
        )
        
        assert exit_code == 4, f"Expected exit 4 for unknown path, got {exit_code}"
        assert data['mode'] is None
        assert data['exit_code'] == 4
        assert 'Unknown scope' in data['reason'] or 'do not match any ring' in data['reason']
    
    def test_no_input_exits_4(self):
        """No input should exit with code 4."""
        stdout, stderr, exit_code = self.run_router("--json")
        
        assert exit_code == 4, f"Expected exit 4 for no input, got {exit_code}"
        # Should have error message in stderr
        assert "Must provide either --nl or --proposed-paths" in stderr
    
    # ===== Forbidden Pattern Tests =====
    
    def test_hard_path_in_core_governance_exits_4(self):
        """Hard paths (/Users/) in core/governance/ should exit 4."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "core/governance/policy_with_/Users/path.md"
        )
        
        assert exit_code == 4, f"Expected exit 4 for hard path, got {exit_code}"
        assert data['exit_code'] == 4
        assert 'Hard paths in governance files' in data['reason']
    
    def test_delete_core_governance_exits_4(self):
        """DELETE operations on core/governance/ should exit 4."""
        data, exit_code = self.run_router_json(
            "--nl", "delete core/governance/old_policy.md"
        )
        
        assert exit_code == 4, f"Expected exit 4 for DELETE governance, got {exit_code}"
        assert data['exit_code'] == 4
        assert 'deletion requires explicit approval' in data['reason']
    
    def test_delete_workflow_exits_4(self):
        """DELETE operations on .github/workflows/ should exit 4."""
        data, exit_code = self.run_router_json(
            "--nl", "remove .github/workflows/old.yml"
        )
        
        assert exit_code == 4
        assert data['exit_code'] == 4
    
    # ===== Mode Requirements Tests =====
    
    def test_hard_mode_has_required_checks(self):
        """HARD mode should include all required checks."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "core/governance/test.md"
        )
        
        assert exit_code == 0
        required = data['required_checks']
        
        # HARD mode must have these checks
        assert 'clean_working_tree' in required
        assert 'invariants_list' in required
        assert 'numbered_plan' in required
        assert 'verification_matrix' in required
        assert 'rollback_plan' in required
        assert 'stop_conditions' in required
        assert 'governance_tests_pass' in required
    
    def test_hard_mode_has_required_labels(self):
        """HARD mode should require governance-change label."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "core/policy.yaml"
        )
        
        assert exit_code == 0
        assert 'governance-change' in data['required_labels']
    
    def test_med_mode_has_required_checks(self):
        """MED mode should include structured checks."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "core_brain/compiler/test.py"
        )
        
        assert exit_code == 0
        required = data['required_checks']
        
        assert 'scope_dependencies' in required
        assert 'implementation_steps' in required
        assert 'tests_defined' in required
        assert 'expected_results' in required
    
    def test_soft_mode_minimal_checks(self):
        """SOFT mode should have minimal checks."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "docs/readme.md"
        )
        
        assert exit_code == 0
        required = data['required_checks']
        
        assert 'traceable' in required
        assert len(required) == 1  # Only traceable
    
    # ===== Highest Ring Priority Tests =====
    
    def test_mixed_paths_uses_highest_ring(self):
        """When multiple paths, should use highest ring (R3 > R2 > R1 > R0)."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "docs/readme.md", "core/governance/test.md"
        )
        
        # core/governance is R3, docs is R0 => should be R3/HARD
        assert exit_code == 0
        assert data['ring'] == 'R3'
        assert data['mode'] == 'HARD'
    
    def test_r2_and_r0_uses_r2(self):
        """R2 should take priority over R0."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "reports/log.txt", "core_brain/test.py"
        )
        
        assert exit_code == 0
        assert data['ring'] == 'R2'
        assert data['mode'] == 'MED'
    
    # ===== JSON Output Schema Tests =====
    
    def test_json_output_has_required_fields(self):
        """JSON output should have all required schema fields."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "docs/test.md"
        )
        
        # Required fields per contract
        assert 'mode' in data
        assert 'ring' in data
        assert 'risk' in data
        assert 'allowed_mutations' in data
        assert 'required_checks' in data
        assert 'required_labels' in data
        assert 'exit_code' in data
        assert 'reason' in data
    
    def test_json_output_types(self):
        """JSON output fields should have correct types."""
        data, exit_code = self.run_router_json(
            "--proposed-paths", "core/test.py"
        )
        
        assert isinstance(data['mode'], str)
        assert isinstance(data['ring'], str)
        assert isinstance(data['risk'], str)
        assert isinstance(data['allowed_mutations'], list)
        assert isinstance(data['required_checks'], list)
        assert isinstance(data['required_labels'], list)
        assert isinstance(data['exit_code'], int)
        assert isinstance(data['reason'], str)
    
    # ===== Natural Language Inference Tests =====
    
    def test_nl_infers_create_operation(self):
        """NL with 'create' should infer CREATE operation."""
        data, exit_code = self.run_router_json(
            "--nl", "create new file docs/guide.md"
        )
        
        assert exit_code == 0
        assert 'CREATE' in data['allowed_mutations']
    
    def test_nl_infers_edit_operation(self):
        """NL with 'edit' should infer EDIT operation."""
        data, exit_code = self.run_router_json(
            "--nl", "edit docs/readme.md to fix typo"
        )
        
        assert exit_code == 0
        # SOFT mode allows EDIT
        assert 'EDIT' in data['allowed_mutations']
    
    def test_nl_extracts_path(self):
        """NL should extract file paths."""
        data, exit_code = self.run_router_json(
            "--nl", "update core/governance/agents.md"
        )
        
        # Should detect core/governance path => R3/HARD
        assert exit_code == 0
        assert data['ring'] == 'R3'


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])
