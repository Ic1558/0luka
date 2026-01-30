#!/usr/bin/env python3
# tools/librarian/scoring.py
# Scoring engine for Librarian actions (Approved v1)

import hashlib
from pathlib import Path
from .utils import file_checksum, short_hash

# Scoring model constants
PASS_THRESHOLD = 70

# Criteria weights
WEIGHT_PATH_COMPLIANCE = 30
WEIGHT_CHECKSUM_DISCIPLINE = 20
WEIGHT_NON_CORE_SAFETY = 25
WEIGHT_ATOMICITY = 15
WEIGHT_TRACEABILITY = 10

WEIGHTS = {
    "path_compliance": WEIGHT_PATH_COMPLIANCE,
    "checksum_discipline": WEIGHT_CHECKSUM_DISCIPLINE,
    "non_core_safety": WEIGHT_NON_CORE_SAFETY,
    "atomicity": WEIGHT_ATOMICITY,
    "traceability": WEIGHT_TRACEABILITY,
}

# Gate definitions
GATE_HARD_FAIL = "HARD_FAIL"   # Score 0 - Block (no override in v1)
GATE_SOFT_FAIL = "SOFT_FAIL"   # Score 1-69 - Block
GATE_WARN = "WARN"            # Score 70-89 - Allow + flag
GATE_OK = "OK"                 # Score 90-100 - Allow

def evaluate_action(action: dict) -> dict:
    """
    Evaluate a Librarian action against scoring criteria.
    
    Returns dict with score, breakdown, gate, reason.
    
    Action dict must contain:
    - src_path (str)
    - dst_path (str)
    - dst_exists (bool)
    - ts_utc (str) - if present
    - action_type (str)
    """
    breakdown = {}
    total_score = 0
    reasons = []
    
    # 1. Path compliance
    src_rel = str(action.get("src_path", ""))
    dst_rel = str(action.get("dst_path", ""))
    
    # Check if paths match scatter→canonical rules
    # For now: assume compliance if dst_path exists and is not in core/
    path_compliance_score = WEIGHT_PATH_COMPLIANCE
    is_core_touch = any(p in src_rel for p in ["core/", "core_brain/", "core_brain/"])
    
    if is_core_touch:
        breakdown["path_compliance"] = 0
        reasons.append("Non-core safety violation: touched core path")
    else:
        breakdown["path_compliance"] = WEIGHT_PATH_COMPLIANCE
    
    # 2. Checksum discipline
    if src_rel and dst_rel and action.get("dst_exists", False):
        # Skip for checksum discipline (already present = idempotent)
        checksum_discipline_score = WEIGHT_CHECKSUM_DISCIPLINE
        breakdown["checksum_discipline"] = checksum_discipline_score
        reasons.append("Checksum matched (idempotent)")
    else:
        # No checksum comparison available without reading both files
        # For v1: assume discipline if ts_utc present
        if action.get("ts_utc"):
            checksum_discipline_score = WEIGHT_CHECKSUM_DISCIPLINE
            breakdown["checksum_discipline"] = checksum_discipline_score
        else:
            checksum_discipline_score = 0
            breakdown["checksum_discipline"] = 0
            reasons.append("Missing ts_utc (traceability issue)")
    
    # 3. Non-core safety (already checked above)
    if is_core_touch:
        non_core_safety_score = 0
        breakdown["non_core_safety"] = 0
    else:
        non_core_safety_score = WEIGHT_NON_CORE_SAFETY
        breakdown["non_core_safety"] = non_core_safety_score
    
    # 4. Atomicity
    # For v1: assume atomic if no partial state indicated
    atomicity_score = WEIGHT_ATOMICITY
    breakdown["atomicity"] = atomicity_score
    
    # 5. Traceability
    ts_utc = action.get("ts_utc", "")
    if ts_utc and "Z" not in ts_utc:  # Catch "Zs" typo
        traceability_score = 0
        breakdown["traceability"] = 0
        reasons.append("ts_utc format breach (Zs typo or invalid)")
    elif not ts_utc:
        traceability_score = 0
        breakdown["traceability"] = 0
        reasons.append("Missing ts_utc")
    else:
        traceability_score = WEIGHT_TRACEABILITY
        breakdown["traceability"] = traceability_score
    
    # Calculate total
    total_score = sum(breakdown.values())
    
    # Determine gate
    if total_score == 0:
        gate = GATE_HARD_FAIL
        gate_reason = "HARD FAIL - Non-negotiable violation"
    elif total_score < PASS_THRESHOLD:
        gate = GATE_SOFT_FAIL
        gate_reason = f"SOFT FAIL - Score {total_score} < {PASS_THRESHOLD}"
    elif total_score < 90:
        gate = GATE_WARN
        gate_reason = f"WARN - Score {total_score} below 90"
    else:
        gate = GATE_OK
        gate_reason = "OK - Full compliance"
    
    return {
        "score": total_score,
        "breakdown": breakdown,
        "gate": gate,
        "reason": gate_reason,
        "details": reasons if total_score < PASS_THRESHOLD else []
    }
