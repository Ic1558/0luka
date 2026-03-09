#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT_REPO = Path(__file__).resolve().parents[2]
if str(ROOT_REPO) not in sys.path:
    sys.path.insert(0, str(ROOT_REPO))

# core.config is fail-closed on missing LUKA_RUNTIME_ROOT at import time.
if not os.environ.get("LUKA_RUNTIME_ROOT"):
    os.environ["ROOT"] = str(ROOT_REPO)
    os.environ["0LUKA_ROOT"] = str(ROOT_REPO)
    os.environ["LUKA_RUNTIME_ROOT"] = tempfile.mkdtemp(prefix="0luka_rt_test_")


class RuntimeProbeTests(unittest.TestCase):
    def _env(self, runtime_root: Path) -> dict[str, str]:
        return {
            "ROOT": str(ROOT_REPO),
            "0LUKA_ROOT": str(ROOT_REPO),
            "LUKA_RUNTIME_ROOT": str(runtime_root),
        }

    def test_health_env_key_present(self) -> None:
        import core.health as health

        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td).resolve()
            with patch.dict(os.environ, self._env(runtime_root), clear=False):
                report = health.check_health(run_tests=False)
        self.assertIn("env", report)
        self.assertIn("git", report["env"])
        self.assertIn("launchd", report["env"])
        self.assertIn("services", report["env"])
        self.assertIn("config_hash", report["env"])

    def test_git_branch_is_string(self) -> None:
        import core.health as health

        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td).resolve()
            with patch.dict(os.environ, self._env(runtime_root), clear=False):
                env = health._probe_env()
        self.assertIsInstance(env["git"]["branch"], str)

    def test_config_hash_present(self) -> None:
        import core.health as health

        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td).resolve()
            with patch.dict(os.environ, self._env(runtime_root), clear=False):
                env = health._probe_env()
        self.assertIsInstance(env["config_hash"], str)
        self.assertTrue(env["config_hash"])

    def test_health_latest_json_contains_env(self) -> None:
        import core.health as health

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "health_latest.json"
            runtime_root = root / "runtime_root"
            with patch.dict(os.environ, self._env(runtime_root), clear=False):
                with patch.object(health, "CACHE_PATH", cache):
                    report = health.check_health(run_tests=False)
                    health._write_json_atomic(health.CACHE_PATH, report)
                    loaded = json.loads(cache.read_text(encoding="utf-8"))
                    self.assertIn("env", loaded)

    def test_env_flag_runs_probe_only(self) -> None:
        import core.health as health

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "health_latest.json"
            runtime_root = root / "runtime_root"
            with patch.dict(os.environ, self._env(runtime_root), clear=False):
                with patch.object(health, "CACHE_PATH", cache):
                    with patch.object(health, "_run_tests") as run_tests:
                        argv = ["core/health.py", "--env", "--json"]
                        with patch("sys.argv", argv):
                            buf = StringIO()
                            with redirect_stdout(buf):
                                rc = health.main()
                        self.assertEqual(rc, 0)
                        run_tests.assert_not_called()


def main() -> int:
    unittest.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
