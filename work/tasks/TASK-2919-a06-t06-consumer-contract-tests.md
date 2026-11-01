---
id: TASK-2919
title: A-06-T06 consumer contract tests for the C8 and completion stubs
spec: SPEC-642
acceptance_criteria: [SPEC-642 AC-3]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T06
branch: s24-a06-t06 (stacked on s24-a06-t05)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

AY's consumer tests against N's C8 and completion stubs, run in the providers' CI.

## Plan

- `backend/tests/contracts/c08_adjustments/test_c08_stub.py`: every C8 operation's one action, 404 and 501, Idempotency-Key on writes, classified fields, clients deny, agent no write, send needs a fresh second factor, flag off, no posting route or posting state.
- `backend/tests/contracts/a06_completion/test_completion_stub.py`: AUD-15/16 operations, classified fields, clients deny, the agent only reads or proposes, passing on SUM the EP's alone, no severity or SUM-conclusion endpoint (C3 cards), Northwind's SUM example, flag off.
- The TypeScript fixture assertions for AUD-15/16/17 arrive with the screens (A-06-T20 onward), against the generated client.

## Progress log

- 2026-11-01: written in abacus-s24, stacked on A-06-T05. Not run.
