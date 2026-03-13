"""Delegated entrypoint placeholder for antigravity_scan.

This file exists to satisfy the runtime wrapper contract path while runtime
source restoration is completed in a later change set.
"""

from __future__ import annotations


def main() -> int:
    # Keep behavior explicit: entrypoint path is restored, logic is not.
    raise SystemExit("antigravity_prod.py placeholder: runtime logic not restored")


if __name__ == "__main__":
    main()
