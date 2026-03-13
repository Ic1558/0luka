# Antigravity Runtime Executor

This directory contains execution-orchestration scaffolding for Antigravity
runtime phases.

## Role

- hold pre-execution validation logic
- build supervised execution plans
- report blockers without mutating live runtime

## Non-goals

- no PM2 operations
- no launchd operations
- no external API execution
