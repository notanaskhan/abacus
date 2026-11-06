---
id: TASK-3338
title: T-03-T19 retire tax.returns_v1, tax.k1_release and questionnaires.v1 for a tax_returns entitlement
spec: SPEC-000  # row (T-03-T19)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: T-03
plan_key: T-03-T19
branch: s28r-t03-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Retire T-02's rollout flags now T-03 has adopted their paths; a firm without the entitlement still gets 404.

## Plan
- Migration 0671: `tax_returns` module, backfill from firms with a flag on.
- Route gates, flag registry, generated `_flags.py`, loader, fixture shell, FeatureGate.
- Tests moved from flag rows to entitlement rows; new `test_t03t19_entitlement.py`.
- Rollback: revert and downgrade 0671.

## Progress log
- 2026-11-06: built. `test_t03t19_entitlement.py` and the T-02, portal-isolation and loaded-slice suites that depended on the flags: 38 passed, 1 xfailed. Web: 3,157 of 3,158 passed; `gates.ac.test.tsx` fails with or without this PR's fixture change, cause not yet established.

## Decisions made during this task
DEC-2329
