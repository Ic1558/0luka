# Antigravity Runtime State Store

This directory contains in-memory artifact store scaffolding for Antigravity
runtime planning.

## Purpose

- provide typed in-memory storage for blocker, evidence, and plan artifacts
- support worker and executor planning flow without live runtime mutation

## Relationship

- consumes artifact models from `runtime/antigravity/artifacts/`
- supports worker and executor planning layers

## Non-goals

- no persistence
- no filesystem writes
- no runtime mutation
- no supervisor integration
