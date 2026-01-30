#!/usr/bin/env python3
# tools/librarian/tests/test_identity_safety.py
# Verification: Assert `compute_move_id` is meta-only (Approved v1 / A1)

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from tools.librarian.utils import compute_move_id

class TestIdentitySafety(unittest.TestCase):
    def test_compute_move_id_is_meta_only(self):
        """
        Approved v1 (A1) Compliance Test:
        Assert that `compute_move_id` NEVER opens or reads the file content.
        It must only use metadata (stat).
        """
        src = Path("dummy_src.txt")
        dst = Path("dummy_dst.txt")
        
        # We mock Path.stat to return dummy metadata
        mock_stat = MagicMock()
        mock_stat.st_size = 1024
        mock_stat.st_mtime_ns = 123456789
        mock_stat.st_ino = 999
        
        # We wrap Path.open and Path.read_bytes to RAISE if called
        # This is the "Safety Trap" for A1 compliance.
        with patch.object(Path, 'stat', return_value=mock_stat), \
             patch.object(Path, 'open', side_effect=RuntimeError("A1 VIOLATION: File content read!")), \
             patch.object(Path, 'read_bytes', side_effect=RuntimeError("A1 VIOLATION: File content read!")), \
             patch.object(Path, 'read_text', side_effect=RuntimeError("A1 VIOLATION: File content read!")):
            
            try:
                move_id = compute_move_id(src, dst)
                print(f"OK: move_id={move_id}")
            except RuntimeError as e:
                self.fail(f"Identity Safety Failed: {e}")
            except Exception as e:
                self.fail(f"Unexpected error: {e}")

if __name__ == "__main__":
    unittest.main()
