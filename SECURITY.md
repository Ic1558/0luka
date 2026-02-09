# Security Policy

## Supported Versions
This repository follows a **phase-gated security model**.

Only the `main` branch is considered supported.
Phase-locked baselines (e.g. Phase 1A immutable baseline) must not be bypassed.

This repository is proprietary and internal-use only. See `LICENSE` and `NOTICE.md`.

## Reporting a Vulnerability
If you discover a security issue, **do not open a public issue**.

Please report privately via one of the following:
- Email: security@theedges.work
- GitHub: open a private security advisory (preferred)

Include:
- A clear description of the issue
- Steps to reproduce (if applicable)
- Potential impact
- Any suggested mitigation

## Response Expectations
- Initial acknowledgment: within **72 hours**
- Status update: within **7 days**
- Fix or mitigation plan will be communicated when validated

## Scope Notes
- Configuration, policy, and contract files under `core/contracts/` are treated
  as **security-sensitive**.
- Any change violating phase scope locks or trust boundaries will be rejected.
