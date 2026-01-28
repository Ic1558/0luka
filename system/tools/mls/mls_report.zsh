#!/usr/bin/env zsh
# Generate a simple MLS HTML report.
set -euo pipefail

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
MLS_DB="${MLS_DB:-$ROOT/g/knowledge/mls_lessons.jsonl}"
OUT_DIR="${OUT_DIR:-$ROOT/g/reports/mls}"
DATE=$(date +%Y%m%d)
OUT_FILE="${OUT_DIR}/mls_report_${DATE}.html"

mkdir -p "$OUT_DIR"

python3 - "$MLS_DB" "$OUT_FILE" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

mls_db = Path(sys.argv[1])
out_file = Path(sys.argv[2])

entries = []
if mls_db.exists():
    with mls_db.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

def parse_time(value: str):
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return datetime.min

entries_sorted = sorted(entries, key=lambda e: parse_time(e.get("timestamp", "")), reverse=True)

by_type = {}
for entry in entries:
    t = entry.get("type", "other")
    by_type[t] = by_type.get(t, 0) + 1

def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

rows = []
for entry in entries_sorted[:200]:
    rows.append(
        "<tr>"
        f"<td>{esc(entry.get('id','-'))}</td>"
        f"<td>{esc(entry.get('type','-'))}</td>"
        f"<td>{esc(entry.get('timestamp','-'))}</td>"
        f"<td>{esc(entry.get('title','-'))}</td>"
        f"<td>{esc(entry.get('description','-'))}</td>"
        "</tr>"
    )

summary_items = "".join(
    f"<li>{esc(k)}: {v}</li>" for k, v in sorted(by_type.items())
)
if not summary_items:
    summary_items = "<li>No lessons found</li>"

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>MLS Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; }}
    th {{ background: #f4f4f4; text-align: left; }}
    .meta {{ color: #666; margin-bottom: 16px; }}
  </style>
</head>
<body>
  <h1>MLS Report</h1>
  <div class=\"meta\">Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}</div>
  <h2>Summary</h2>
  <ul>
    {summary_items}
  </ul>
  <h2>Recent Lessons</h2>
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>Type</th>
        <th>Timestamp</th>
        <th>Title</th>
        <th>Description</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows) if rows else '<tr><td colspan="5">No lessons</td></tr>'}
    </tbody>
  </table>
</body>
</html>
"""

out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(html, encoding="utf-8")
print(str(out_file))
PY
