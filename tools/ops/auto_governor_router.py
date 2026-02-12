#!/usr/bin/env python3
"""
Auto-Adaptive Governor Router
Universal, tool-agnostic governance mode selector

Usage:
    python3 tools/ops/auto_governor_router.py --nl "edit core/governance/x.md" --json
    python3 tools/ops/auto_governor_router.py --proposed-paths core/file.py docs/readme.md --json

Exit Codes:
    0: OK - Valid plan produced
    2: Partial - Some constraints cannot be satisfied
    3: Designed - Plan created, requires human approval
    4: Contract violation - Invalid inputs or unknown scope
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install: pip3 install pyyaml", file=sys.stderr)
    sys.exit(4)


class GovernorRouter:
    """Tool-agnostic governance router based on file scope detection."""
    
    def __init__(self, contract_path: str):
        """Load governance contract."""
        with open(contract_path, 'r') as f:
            self.contract = yaml.safe_load(f)
        
        self.rings = self.contract['rings']
        self.modes = self.contract['modes']
        self.forbidden_patterns = self.contract['forbidden_patterns']
        self.exit_codes = self.contract['exit_codes']
    
    def detect_scope(self, paths: List[str]) -> Tuple[str, str, str]:
        """
        Detect ring, mode, and risk from file paths.
        
        Returns: (ring, mode, risk)
        Raises: ValueError if scope cannot be classified
        """
        if not paths:
            raise ValueError("No paths provided for scope detection")
        
        # Find highest-risk ring touched
        detected_ring = None
        detected_mode = None
        
        for path in paths:
            for ring_name in ['R3', 'R2', 'R1', 'R0']:
                ring = self.rings[ring_name]
                for ring_path in ring['paths']:
                    if path.startswith(ring_path):
                        # Higher ring number = higher priority
                        if detected_ring is None or int(ring_name[1]) > int(detected_ring[1]):
                            detected_ring = ring_name
                            detected_mode = ring['default_mode']
                        break
        
        if detected_ring is None:
            raise ValueError(f"Unknown scope: paths {paths} do not match any ring definition")
        
        # Map ring to risk
        risk_map = {
            'R3': 'Critical',
            'R2': 'High',
            'R1': 'Medium',
            'R0': 'Low'
        }
        risk = risk_map[detected_ring]
        
        return detected_ring, detected_mode, risk
    
    def check_forbidden_patterns(self, paths: List[str], operations: List[str]) -> Optional[Dict]:
        """
        Check for forbidden patterns.
        
        Returns: Violation dict if found, None otherwise
        """
        for pattern_rule in self.forbidden_patterns:
            pattern = pattern_rule['pattern']
            scope = pattern_rule['scope']
            
            # Check if any path matches scope and contains pattern
            for path in paths:
                if path.startswith(scope):
                    # DELETE is an operation-level control.
                    if pattern == "DELETE" and "DELETE" in operations:
                        return {
                            'reason': pattern_rule['reason'],
                            'exit_code': pattern_rule['exit_code'],
                            'path': path,
                            'pattern': pattern
                        }

                    # Other patterns are matched against the path as regex.
                    if pattern != "DELETE" and re.search(pattern, path):
                        return {
                            'reason': pattern_rule['reason'],
                            'exit_code': pattern_rule['exit_code'],
                            'path': path,
                            'pattern': pattern
                        }
        
        return None
    
    def infer_operations(self, nl_text: str) -> List[str]:
        """Infer operations from natural language text."""
        operations = []
        
        nl_lower = nl_text.lower()
        
        if any(word in nl_lower for word in ['create', 'add', 'new']):
            operations.append('CREATE')
        if any(word in nl_lower for word in ['edit', 'modify', 'update', 'change', 'fix']):
            operations.append('EDIT')
        if any(word in nl_lower for word in ['rename', 'move']):
            operations.append('RENAME')
        if any(word in nl_lower for word in ['delete', 'remove', 'drop']):
            operations.append('DELETE')
        
        # Default to EDIT if nothing detected
        if not operations:
            operations.append('EDIT')
        
        return operations
    
    def infer_paths(self, nl_text: str) -> List[str]:
        """Infer file paths from natural language text."""
        paths = []
        
        # Simple heuristic: look for words containing /
        words = nl_text.split()
        for word in words:
            if '/' in word:
                # Clean up quotes and punctuation
                clean_word = word.strip('",\'.:;')
                paths.append(clean_word)
        
        return paths
    
    def route(self, nl_text: Optional[str] = None, proposed_paths: Optional[List[str]] = None) -> Dict:
        """
        Route a request to appropriate governance mode.
        
        Args:
            nl_text: Natural language request
            proposed_paths: Explicit list of paths (overrides NL inference)
        
        Returns:
            Dict with mode, ring, risk, allowed_mutations, required_checks, exit_code, reason
        """
        try:
            # Determine paths
            if proposed_paths:
                paths = proposed_paths
                operations = ['EDIT']  # Default when paths are explicit
            elif nl_text:
                paths = self.infer_paths(nl_text)
                operations = self.infer_operations(nl_text)
            else:
                return {
                    'mode': None,
                    'ring': None,
                    'risk': None,
                    'allowed_mutations': [],
                    'required_checks': [],
                    'required_labels': [],
                    'exit_code': 4,
                    'reason': 'No input provided (neither --nl nor --proposed-paths)'
                }
            
            if not paths:
                return {
                    'mode': None,
                    'ring': None,
                    'risk': None,
                    'allowed_mutations': [],
                    'required_checks': [],
                    'required_labels': [],
                    'exit_code': 4,
                    'reason': 'Cannot infer paths from input'
                }
            
            # Check forbidden patterns
            violation = self.check_forbidden_patterns(paths, operations)
            if violation:
                return {
                    'mode': None,
                    'ring': None,
                    'risk': 'Critical',
                    'allowed_mutations': [],
                    'required_checks': [],
                    'required_labels': [],
                    'exit_code': violation['exit_code'],
                    'reason': f"{violation['reason']}: {violation['path']} (pattern: {violation['pattern']})"
                }
            
            # Detect scope
            ring, mode, risk = self.detect_scope(paths)
            
            # Get mode config
            mode_config = self.modes[mode]
            
            # Build response
            return {
                'mode': mode,
                'ring': ring,
                'risk': risk,
                'allowed_mutations': mode_config['allowed_mutations'],
                'required_checks': mode_config['required_checks'],
                'required_labels': mode_config.get('required_labels', []),
                'command_plan': {
                    'steps': [
                        f"Detected scope: {', '.join(paths)}",
                        f"Mode: {mode} (Ring: {ring}, Risk: {risk})",
                        f"Required checks: {', '.join(mode_config['required_checks'])}"
                    ],
                    'verification': mode_config['required_checks']
                },
                'exit_code': 0,
                'reason': f"Classified as {mode} mode based on {ring} ring paths"
            }
        
        except ValueError as e:
            return {
                'mode': None,
                'ring': 'X',
                'risk': 'Critical',
                'allowed_mutations': [],
                'required_checks': [],
                'required_labels': [],
                'exit_code': 4,
                'reason': str(e)
            }
        except Exception as e:
            return {
                'mode': None,
                'ring': None,
                'risk': None,
                'allowed_mutations': [],
                'required_checks': [],
                'required_labels': [],
                'exit_code': 4,
                'reason': f"Router error: {str(e)}"
            }


def main():
    parser = argparse.ArgumentParser(
        description='Auto-Adaptive Governor Router (Universal, Tool-Agnostic)'
    )
    parser.add_argument(
        '--nl',
        type=str,
        help='Natural language request (e.g., "edit core/governance/x.md")'
    )
    parser.add_argument(
        '--proposed-paths',
        nargs='+',
        help='Explicit list of file paths to classify'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '--contract',
        type=str,
        default='core/governance/auto_governor_contract.yaml',
        help='Path to governance contract (default: core/governance/auto_governor_contract.yaml)'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.nl and not args.proposed_paths:
        print("ERROR: Must provide either --nl or --proposed-paths", file=sys.stderr)
        sys.exit(4)
    
    # Find contract (support running from repo root or tools/ops/)
    contract_path = Path(args.contract)
    if not contract_path.exists():
        # Try relative to script location
        script_dir = Path(__file__).parent.parent.parent
        contract_path = script_dir / args.contract
    
    if not contract_path.exists():
        print(f"ERROR: Contract not found at {args.contract}", file=sys.stderr)
        sys.exit(4)
    
    # Route request
    router = GovernorRouter(str(contract_path))
    result = router.route(nl_text=args.nl, proposed_paths=args.proposed_paths)
    
    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Mode: {result['mode']}")
        print(f"Ring: {result['ring']}")
        print(f"Risk: {result['risk']}")
        print(f"Allowed Mutations: {', '.join(result['allowed_mutations'])}")
        print(f"Required Checks: {', '.join(result['required_checks'])}")
        if result['required_labels']:
            print(f"Required Labels: {', '.join(result['required_labels'])}")
        print(f"Exit Code: {result['exit_code']}")
        print(f"Reason: {result['reason']}")
    
    sys.exit(result['exit_code'])


if __name__ == '__main__':
    main()
