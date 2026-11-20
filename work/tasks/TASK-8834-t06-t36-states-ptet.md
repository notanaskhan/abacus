---
id: TASK-8834
title: "T-06-T36: States and PTET service"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-t06t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T36
---

## Objective
Approving sourcing resolves the TXP-10 review point once, Undo inside 10 seconds writes sourcing.undone, and Feld's state credit reads 16,025.

## Done
- tax/states_service.py (views, sourcing propose/approve/undo, PTET updates and credits, gap/unmapped issues)
- TXP-09 routes live + sourcing:approve route
- activity_reviewed
- tests/unit/tax/test_t06t36_states_service.py
- DEC-5836

## Progress log
- `2026-11-20` — Plan (amber): service, routes, tests; no migration; rollback = revert. Tests at the end pass.
