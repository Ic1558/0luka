from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.outbox_writer import write_result_to_outbox


def main() -> int:
    os.environ.setdefault("0LUKA_ROOT", str(Path(__file__).resolve().parents[2]))
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "interface/outbox").mkdir(parents=True, exist_ok=True)
        map_path = root / "map.yaml"
        map_path.write_text(
            "version: '1'\n"
            "hosts:\n"
            "  default:\n"
            "    root: '${0LUKA_ROOT}'\n"
            "refs:\n"
            "  'ref://interface/outbox': '${root}/interface/outbox'\n",
            encoding="utf-8",
        )
        result = {
            "task_id": "phase1e_hardpath",
            "status": "ok",
            "summary": "read " + "/" + "Users/icmini/private.txt",
            "outputs": {"json": {}, "artifacts": []},
            "evidence": {"logs": [], "commands": ["noop"]},
            "provenance": {"hashes": {"inputs_sha256": "a", "outputs_sha256": "b"}},
        }
        out_path, envelope = write_result_to_outbox(result, ref_map_path=str(map_path))
        text = out_path.read_text(encoding="utf-8")
        loaded = json.loads(text)
        assert loaded["status"] == "error"
        assert "hardpath_detected" in loaded["summary"]
        assert "/" + "Users/" not in text
        assert "file:///" + "Users/" not in text
        assert envelope["task_id"] == "phase1e_hardpath"
    print("test_phase1e_no_hardpath_in_result: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
