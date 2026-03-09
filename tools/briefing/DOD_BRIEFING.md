# DoD / PPR Briefing (autoload contract)

## Always do this at task start (Discover)
1) Read DoD template:
- docs/dod/DOD_TEMPLATE.md
2) Read the relevant phase DoD:
- docs/dod/DOD__PHASE_*.md (choose matching phase)

## Frozen-zone rules (critical)
If you change anything under:
- docs/dod/**
- core/governance/**

You MUST do all 4:
1) python3 tools/ops/governance_file_lock.py --build-manifest
2) git add docs/dod/ core/governance/governance_lock_manifest.json
3) git commit message includes: [governance-change]
4) PR has label: governance-change

Otherwise governance_gate will block.
