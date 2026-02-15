import yaml
import pytest
from pathlib import Path

CONTRACT_PATH = Path("core/governance/auto_governor_contract.yaml")

def test_contract_exists():
    assert CONTRACT_PATH.exists()

def test_contract_schema():
    with open(CONTRACT_PATH) as f:
        contract = yaml.safe_load(f)
    
    assert "schema_version" in contract
    assert "rings" in contract
    assert "modes" in contract
    assert "forbidden_patterns" in contract
    assert "exit_codes" in contract
    
    # Check rings
    for ring in ["R3", "R2", "R1", "R0"]:
        assert ring in contract["rings"]
        assert "paths" in contract["rings"][ring]
        assert "default_mode" in contract["rings"][ring]
    
    # Check modes
    for mode in ["HARD", "MED", "SOFT"]:
        assert mode in contract["modes"]
        assert "required_checks" in contract["modes"][mode]
        assert "allowed_mutations" in contract["modes"][mode]

def test_forbidden_patterns_escaped():
    with open(CONTRACT_PATH) as f:
        contract = yaml.safe_load(f)
        
    for pattern in contract["forbidden_patterns"]:
        p = pattern["pattern"]
        # Ensure literal /Users/ string is NOT present in the value if it was meant to be escaped
        # But wait, yaml.safe_load parses escapes! So in memory it WILL be /Users/
        # The test should check the raw file content for literal /Users/
        pass

def test_raw_content_no_hard_paths():
    """Verify raw file content does not contain literal /Users/ string."""
    content = CONTRACT_PATH.read_text()
    # We expect \x2FUsers\x2F or similar, not /Users/
    assert "/Users/" not in content, "Contract file contains literal /Users/ string"

