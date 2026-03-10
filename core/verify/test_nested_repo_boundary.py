from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QS_ROOT = ROOT / "repos" / "qs"


def _git_output(*args: str) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def test_outer_repo_does_not_track_nested_qs_contents() -> None:
    tracked = _git_output("ls-files", "repos/qs")
    assert tracked == [], (
        "Outer repo must not track files inside repos/qs; "
        f"found tracked paths: {tracked}"
    )


def test_nested_qs_repo_is_treated_as_separate_checkout_when_present() -> None:
    if not QS_ROOT.exists():
        return

    assert (QS_ROOT / ".git").exists(), (
        "If repos/qs exists in the outer workspace, it must remain a nested "
        "git checkout rather than tracked outer-repo content."
    )
