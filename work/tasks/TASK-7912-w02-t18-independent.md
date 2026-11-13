---
id: TASK-7912
title: W-02-T18 Independent AC tests for W-02-T06, T09, T10, T11
plan_key: W-02-T18
spec: SPEC-653
acceptance_criteria: [AC-V1, AC-V2, AC-V3, AC-C3, AC-A6]  # walled leaks fail; inaccessible picker rows fail
risk_zone: amber
status: in-review
branch: w02-t18-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
ADR-078 suite: membership and locked verdicts, walled omission from rows, counts and search,
picker visibility and 404 on an unlisted record, insert-only items and soft delete, the season
counts footing.

## Plan
- Test: `backend/tests/unit/workbench/test_w02t18_independent.py` (no production code).

## Partial
- Solo edition: written in this session, not "N's session" (AMENDMENT-solo).
- The live-database walls (RLS, `visible()`) stay in the integration suites; here the services'
  own verdicts are driven with stand-ins.

## Progress log
- 2026-11-13: written, not run (S42 end pass).
