# Governance Operations

This directory contains the operational tooling and policies for the 0luka Governance System.

## Key Files
*   `gate_runnerd.py`: The Judicial Daemon (v0.5.0).
*   `ontology.yaml`: The Policy Source of Truth (in `core/governance`).
*   `verify_v*.py`: Certification test suites.

## Policies
*   **[Script Promotion SOP](promotion_sop.md)**: Rules for Retention vs. Catalog promotion. Strict 6-Gate policy for tools.

## Enforcers
*   `enforce_script_policy.zsh`: Automates the "Retention Rule" by moving loose scripts to `observability/antigravity_tmp/scripts/`.
