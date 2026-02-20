from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import subprocess


@dataclass(frozen=True)
class SentryResult:
    ok: bool
    reason: str = ""


class SentryViolation(RuntimeError):
    pass


def _probe_dispatcher_launchd(
    *,
    label: str = "com.0luka.dispatcher",
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> None:
    """
    Probe launchd for dispatcher status.
    We keep this isolated and injectable for tests.
    """
    # We intentionally avoid shell expansion.
    # launchctl will return non-zero if label isn't loaded.
    cmd = ["launchctl", "print", f"gui/{_uid()}/{label}"]
    cp = runner(cmd, capture_output=True, text=True)
    if cp.returncode != 0:
        raise SentryViolation(f"dispatcher_not_running:{label}")

    out = (cp.stdout or "") + "\n" + (cp.stderr or "")
    # Heuristic: look for "state = running" (best-effort)
    if "state = running" not in out:
        # Still treat as violation because we want fail-closed.
        raise SentryViolation(f"dispatcher_not_running_state:{label}")


def _uid() -> str:
    # Avoid importing os.getuid in a way that complicates tests
    import os
    return str(os.getuid())


def run_preflight(
    *,
    root: Path,
    require_activity_feed: bool = True,
    probe_dispatcher: bool = True,
    dispatcher_label: str = "com.0luka.dispatcher",
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> SentryResult:
    """
    Minimal deterministic Sentry preflight (Phase 9B v0).

    Invariants:
      1) root exists
      2) activity_feed.jsonl exists (if required)
      3) no .git/index.lock
      4) dispatcher is running (if probe enabled)
    """
    root = Path(root)

    if not root.exists():
        raise SentryViolation("root_missing")

    if require_activity_feed:
        feed = root / "observability" / "logs" / "activity_feed.jsonl"
        if not feed.exists():
            raise SentryViolation("activity_feed_missing")

    lock = root / ".git" / "index.lock"
    if lock.exists():
        raise SentryViolation("git_index_lock_present")

    if probe_dispatcher:
        _probe_dispatcher_launchd(label=dispatcher_label, runner=runner)

    return SentryResult(ok=True, reason="ok")
