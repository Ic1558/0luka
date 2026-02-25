# Proof: Codex Canonical Server Verification (20260225T204043Z)

Timestamp UTC: 2026-02-25T20:40:43Z
Commit SHA: 92e7ca289bc8af449099a15c8f7a685cd9843db7

## Step 1: Sync main (run in /Users/icmini/0luka)

Command:

```bash
cd /Users/icmini/0luka && git switch main && git pull --ff-only
```

Output:

```text
Already on 'main'
Your branch is up to date with 'origin/main'.
Already up to date.
```

## Verify commands + outputs

### a)

Command:

```bash
zsh -n tools/ops/check_codex_overlap.zsh ; echo "exit=$?"
```

Output:

```text
exit=0
```

### b)

Command:

```bash
tools/ops/check_codex_overlap.zsh ; echo "exit=$?"
```

Output:

```text
CANONICAL_CODEX=/Applications/Codex.app/Contents/Resources/codex
PID      | TYPE          | COMMAND
---------+---------------+--------------------------------------------------------------
62443    | canonical     | /Applications/Codex.app/Contents/Resources/codex app-server --analytics-default-enabled

OK: single canonical codex app-server
exit=0
```

### c)

Command:

```bash
ps aux | rg -n "codex app-server" | rg -v "rg -n|/bin/zsh -lc" | wc -l
```

Output:

```text
       1
```

### d)

Command:

```bash
launchctl print gui/$(id -u)/com.0luka.notebook_sync 2>&1 | head -n 5
```

Output:

```text
Bad request.
Could not find service "com.0luka.notebook_sync" in domain for user gui: 501
```
