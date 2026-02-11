# pattern-killer

Purpose
- Detect, rewrite, and score repetitive low-signal text patterns deterministically.

Mandatory Read: NO

Inputs
- Text from `--input-file` or stdin
- Pattern DB from `--patterns` (JSONL)

Outputs
- JSON to stdout with deterministic keys/order and matched pattern ids
- Optional rewritten output file via atomic write when `rewrite --apply --output-file` is used

Caps
- Local-only deterministic processing
- Read pattern DB + input text
- Atomic write for explicit rewrite output target

Forbidden actions
- Network calls
- External command execution
- Mutating files outside explicit `--output-file`
