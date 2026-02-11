# Test Matrix — Cole-Run

| Case | Expected |
|---|---|
| `list` with unsorted runs | sorted lexicographic output |
| `latest` with runs | max(sorted_lexicographic) |
| `show <run_id>` existing file | JSON with redacted safe content |
| `show ../../etc/passwd` | reject `invalid_run_id` |
| static scan | no write ops or network usage |
