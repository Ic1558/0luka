# Antigravity Runtime Engine

Artifact emitter for the Antigravity runtime planning layer.

## Purpose

- emit blocker artifacts to the in-memory store
- emit evidence artifacts to the in-memory store
- emit plan artifacts to the in-memory store

## Relationship

- uses `state/artifact_store.py` as the in-memory sink
- provides additive artifact output for worker and executor planning layers

## Non-goals

- no subprocess calls
- no PM2 or launchd interactions
- no live runtime mutation
- no execution approval changes
- no external API calls
