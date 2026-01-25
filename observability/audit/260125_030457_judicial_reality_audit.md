# Judicial Reality Audit

- Generated: 2026-01-25T03:04:57+07:00
- Root: /Users/icmini/0luka

## 0) Existence + Layout
```text
total 8
drwxr-xr-x   13 icmini  staff    416 Jan 25 00:52 .
drwxr-xr-x@ 405 icmini  staff  12960 Jan 25 02:57 ..
drwxr-xr-x    5 icmini  staff    160 Jan 24 00:18 .0luka
drwxr-xr-x@  15 icmini  staff    480 Jan 25 03:02 .git
-rw-r--r--@   1 icmini  staff    135 Jan 24 01:03 .gitignore
drwxr-xr-x@   8 icmini  staff    256 Jan 25 02:55 .opencode
drwxr-xr-x@   3 icmini  staff     96 Jan 24 01:21 .openwork
drwxr-xr-x    2 icmini  staff     64 Jan 23 12:16 .tmp
drwxr-xr-x@   7 icmini  staff    224 Jan 24 02:56 .venv
drwxr-xr-x@   9 icmini  staff    288 Jan 24 06:13 core
drwxr-xr-x@   9 icmini  staff    288 Jan 25 03:04 observability
drwxr-xr-x@   4 icmini  staff    128 Jan 24 06:13 ops
drwxr-xr-x@   9 icmini  staff    288 Jan 25 02:29 runtime
```

## 1) Key Paths Present?
```text
OK  /Users/icmini/0luka/runtime/sock
OK  /Users/icmini/0luka/runtime/sock/gate_runner.sock
OK  /Users/icmini/0luka/core/governance/ontology.yaml
OK  /Users/icmini/0luka/observability/stl/evidence
OK  /Users/icmini/0luka/observability/stl/tasks/open
OK  /Users/icmini/0luka/ops/governance
OK  /Users/icmini/0luka/ops/governance/handlers
```

## 2) Socket Reality (owner/perm + listener)
```text
srw-rw----@ 1 icmini  staff  0 Jan 25 02:40 /Users/icmini/0luka/runtime/sock/gate_runner.sock
Python    51516 icmini    3u  unix 0xda44c075ee55d7b4      0t0      /Users/icmini/0luka/runtime/sock/gate_runner.sock
```

## 3) Protocol Framing Risk Scan
- Searching for recv(4096), json.loads(data), single-shot reads
```text
