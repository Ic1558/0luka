**Status:** ACTIVE
**Version:** 1.0
**Updated:** 2026-01-28

---

## Overview

MLS (Machine Learning System) captures lessons learned from successes, failures, and patterns discovered during system work.

What it does:
- Captures lessons (manual or automated)
- Organizes by type (solution/failure/pattern)
- Supports search and summaries
- Generates HTML reports

---

## Quick Start

### Capture a Lesson

```bash
~/0luka/system/tools/mls/mls_capture.zsh solution \
  "Title of what worked" \
  "Description of the solution" \
  "Additional context or details"
```

### Search Lessons

```bash
# Search all lessons
~/0luka/system/tools/mls/mls_search.zsh "keyword"

# Filter by type
~/0luka/system/tools/mls/mls_search.zsh "sync" solution
~/0luka/system/tools/mls/mls_search.zsh "conflict" failure
```

### Generate Report

```bash
~/0luka/system/tools/mls/mls_report.zsh
open ~/0luka/g/reports/mls/mls_report_$(date +%Y%m%d).html
```

---

## Lesson Types

1) **Solution** - Something that worked well and should be repeated
2) **Failure** - Something that failed (learn from it)
3) **Pattern** - Reusable approach discovered
4) **Anti-pattern** - Behavior to avoid
5) **Improvement** - Enhancement made to the system

---

## File Structure

```
~/0luka/g/knowledge/
├── mls_lessons.jsonl       # All lessons (append-only)
└── mls_index.json          # Summary stats

~/0luka/g/reports/mls/
└── mls_report_YYYYMMDD.html

~/0luka/system/tools/mls/
├── mls_capture.zsh          # Capture new lesson
├── mls_search.zsh           # Search lessons
├── mls_query.py             # Query summary/recent/search
└── mls_report.zsh           # Generate HTML report
```

---

## Auto-Capture (Optional)

If you later wire MLS auto-capture into bridge/dispatch flows, call `mls_capture.zsh`
when a result is verified as a solution/failure/pattern. This guide assumes manual
capture unless automation is explicitly added.

---

## Query Examples

```bash
python3 ~/0luka/system/tools/mls/mls_query.py summary
python3 ~/0luka/system/tools/mls/mls_query.py recent --limit 10 --format table
python3 ~/0luka/system/tools/mls/mls_query.py search --query "dashboard" --format json
```
