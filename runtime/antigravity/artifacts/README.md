# Antigravity Artifact Models

This directory contains analysis-layer artifact models for Antigravity runtime
planning.

## Purpose

- define structured blocker records
- define evidence reference records
- define remediation plan records

## Relationship to executor contract

These models provide data structures consumed by the executor contract and
related planning artifacts. They do not execute runtime actions.

## Relationship to approval workflow

Artifacts support approval and governance analysis. They do not grant execution
approval by themselves.

## Relationship to broker auth lane

Broker auth remains a separate ops lane. These models may reference broker auth
evidence but do not merge broker auth with runtime architecture execution.

## Non-goals

- no runtime mutation
- no deployment behavior
- no supervisor integration
