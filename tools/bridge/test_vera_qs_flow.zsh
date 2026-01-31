#!/usr/bin/env zsh
# 0luka Vera-QS v0.1 Dry-Run Simulation
# Scenario: Foreman submits a model. Vera-QS validates Material & Quantity fields.

set -e

# Colors for UX
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "${CYAN}--- STARTING VERA-QS v0.1 DRY-RUN ---${NC}"
echo "Domain: BIM / Quantity Surveying"
echo "TRC_ID: TRC-QS-MOCK-001"
echo ""

# 1. LIAM (Architect) - SPECIFICATION
echo "${YELLOW}[Liam]${NC} Specification for QS Audit..."
cat <<EOF
[Liam]
I am defining the Audit Spec for 'Ground Floor Slab' (IFC-GS-01).
- scope: "Material Compliance & Quantity Presence"
- registry: "skills/vera-qs/references/material_registry.md"
- requirement: "All IfcSlab must have C-01 classification."

TaskSpec: interface/inbox/tasks/QS-AUDIT-001.json
EOF

echo ""

# 2. VERA-QS (Validator) - INSPECTION
echo "${YELLOW}[Vera]${NC} BIM/QS Inspection Phase..."
echo "Extracting IFC Data via IfcOpenShell (Pattern Simulation)..."

# Simulate a failure case (Material Mismatch)
echo "${RED}[Vera]${NC} Discrepancy Found."
cat <<EOF
[Vera]
I am auditing Evidence from 'GroundFloor.ifc' against QS-AUDIT-001.

Discrepancy Detail:
- GUID: 3z9W_T55XC_Q9z_... (IfcSlab)
- Material found: "Generic Concrete"
- Expected: "C-01" (Reinforced Concrete 30MPa)

Checklist:
- [ ] Material Match: FAIL (Unauthorized code 'Generic')
- [x] Classification Check: PASS (UniClass-2015 assigned)
- [x] Quantity Existence: PASS (NetVolume = 45.2m3)
- [x] GlobalId Integrity: PASS

Verdict Block:
verdict: FAIL
reason:
  - "Slab GUID-3z9W... uses 'Generic Concrete' instead of authorized 'C-01'."
  - "QS Validation failed due to Material Registry mismatch."
trace_id: TRC-QS-MOCK-001
validator: Vera-QS
call_sign: [Vera]
timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

echo ""
echo "${RED}--- VERDICT ISSUED: FAIL ---${NC}"
echo ""

# 3. GMX (Sovereign) - GOVERNANCE
echo "${YELLOW}[GMX]${NC} Governance Decision..."
cat <<EOF
[GMX]
Reviewed [Vera-QS] verdict for TRC-QS-MOCK-001.

Action:
status: REJECTED
reason: "Material non-compliance detected by Vera-QS. Resubmit with corrected IFC attributes."
trace_id: TRC-QS-MOCK-001
call_sign: [GMX]
EOF

echo ""
echo "${YELLOW}--- VERA-QS FLOW: REJECTED (SAFE) ---${NC}"
