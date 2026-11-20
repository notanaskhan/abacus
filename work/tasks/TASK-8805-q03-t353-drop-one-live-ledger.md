---
id: TASK-8805
title: "Q-03-T353: Call-off A-09 OQ-9: contract step dropping connections_one_live_ledger"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q03t353
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-03-T353
---

## Objective
The contract-step migration passes the expand-only guard with both approvals and the rehearsal.

## Done
- Migration 0990 (on 0987) drops connections_one_live_ledger; downgrade recreates it
- one-live-ledger rule held by connection_coverage_one_live (0897) with the same liveness
- repository docstring updated
- integration test test_q03t353_drop_one_live_ledger.py
- PR labelled contract-step (solo: one approval, AMENDMENT-solo item 2)

## Progress log
- `2026-11-20` — Plan (red): migration, docstring, test, rollback = downgrade. Rehearsal (schema_check up/down/up) and the guard run at the S52 end pass.
