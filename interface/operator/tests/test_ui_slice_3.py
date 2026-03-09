from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _html_text() -> str:
    return (ROOT / "interface" / "operator" / "templates" / "mission_control.html").read_text(encoding="utf-8")

def test_drilldown_logic_present() -> None:
    html = _html_text()
    assert "drilldown-content" in html
    assert "toggleDrilldown" in html
    assert "drilldown-trigger" in html

def test_queue_grouping_logic_present() -> None:
    html = _html_text()
    assert "group-header" in html
    assert "groups = {" in html
    assert "'queued': []" in html
    assert "groupName" in html

def test_lane_ux_improvements_present() -> None:
    html = _html_text()
    assert "lane-expiry" in html
    assert "expiry-expired" in html
    assert "expiry-future" in html
    assert "getExpiryClass" in html
    assert "getExpiryText" in html

def test_polling_visibility_present() -> None:
    html = _html_text()
    assert "sync-indicator" in html
    assert "setSyncing" in html
    assert "SYNCING..." in html

def test_robust_ui_states_present() -> None:
    html = _html_text()
    assert "PANEL_EMPTY" in html
    assert "No data available" in html
    assert "DASHBOARD CONNECTION LOST" in html
