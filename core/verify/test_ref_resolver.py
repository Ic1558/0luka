from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.ref_resolver import resolve_path, resolve_ref


def _assert_raises(fn, expected):
    try:
        fn()
    except expected:
        return
    raise AssertionError(f"expected {expected.__name__}")


def main() -> int:
    repo = resolve_ref("ref://repo/0luka")
    assert repo["uri"].startswith("file://"), repo
    repo_path = resolve_path("ref://repo/0luka")
    assert repo_path.name == "0luka", repo_path

    _assert_raises(lambda: resolve_ref("ref://unknown"), KeyError)

    with tempfile.TemporaryDirectory() as td:
        map_path = Path(td) / "map.yaml"
        map_path.write_text(
            "version: '1'\n"
            "hosts:\n"
            "  default:\n"
            "    root: '${HOME}/0luka'\n"
            "refs:\n"
            "  'ref://bad': '${root}/../escape'\n",
            encoding="utf-8",
        )
        _assert_raises(lambda: resolve_ref("ref://bad", map_path=str(map_path)), ValueError)

    print("test_ref_resolver: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
