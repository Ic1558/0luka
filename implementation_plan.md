# Implementation Plan: Fix MD040 in 0luka.md

## Problem

Markdownlint rule `MD040/fenced-code-language` is triggered because `0luka.md` contains fenced code blocks (` ``` `) that do not specify a language identifier. The lint explicitly flagged line 23, but several other code blocks in the document also lack language tags.

## Proposed Solution

Update all fenced code blocks in `0luka.md` that are missing a language identifier to use ` ```text `. Specifically:

- Line 23: Architecture diagram (ASCII art) -> ` ```text `
- Line 81: Directory structure tree -> ` ```text `
- Line 175: Identity invariant rule -> ` ```text `
- Line 195: 5-Stage Loop list -> ` ```text `
- Line 263: Execution flow diagram -> ` ```text `
- Line 334: Agent monitoring tabular data -> ` ```text `

## Steps

1. Discover phase already completed: inspected `0luka.md` and observed missing language tags on lines 23, 81, 175, 195, 263, 334.
2. Formulate implementation plan and present for approval.
3. DRY-RUN: Check changes via replace tool and verify markdown parsing does not break. We will apply the changes locally.
4. VERIFY: Document changes in `walkthrough.md` and check `git diff`.
5. RUN: Finalize changes and execute any save commands if necessary.
