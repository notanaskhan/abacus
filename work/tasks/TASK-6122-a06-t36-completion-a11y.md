---
id: TASK-6122
title: "A-06-T36 accessibility and keyboard for the completion screens' artboards"
spec: SPEC-000  # row (A-06-T36)
acceptance_criteria: [AC-1]
risk_zone: green
status: done
epic: A-06
plan_key: A-06-T36
branch: s30-a06-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Parity, accessibility and keyboard for the 27 artboards of AUD-15, AUD-16, AUD-17 and AUD-20: Tier C report, Tier C locks, Tier D geometry.

## Plan
- `apps/web/e2e/screens/AUD-completion-a11y.spec.ts`: axe on every artboard of the four screens in fixture mode (serious and critical block, DEC-11); Escape closes a dialog and focus returns to its opener; Tab moves through more than three distinct stops without sticking.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). eslint and prettier clean.

## Decisions made during this task
None.
