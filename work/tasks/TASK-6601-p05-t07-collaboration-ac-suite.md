---
id: TASK-6601
title: "P-05-T07: acceptance suite for comments v2 and to-dos, written from the SPEC and the 501 stubs"
spec: SPEC-650
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-9, AC-10, AC-11, AC-12, AC-13, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30, AC-39]
risk_zone: amber
status: in-review
branch: s34-p05-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-05-T07
---

## Objective
Black-box acceptance tests (HTTP, real database) for SPEC-650's comments and to-dos, written from
the SPEC and the P-05-T03 stubs before P-05-T05/T06; against the stubs every test answers 501.

## Plan (amber)
1. `backend/tests/integration/backfill/p05_support.py`: the Northwind world (five members on two
   engagements, a non-member, a walled member, a firm admin, a client contact; `collaboration.v2`
   on through `feature_flag_states`).
2. `test_p05t07_comments_ac.py`: AC-1 to AC-7, AC-9 to AC-13, AC-16, INV-1, INV-3, INV-4, AC-39.
3. `test_p05t07_todos_ac.py`: AC-17 to AC-30 and AC-39, dates relative to the business date.
4. No production code, no migration, no registry edit. Rollback: delete the three files.

## Progress log
- `2026-11-10` — Written (solo independence: from the SPEC and stubs, before the services). Not
  run (end pass). Gaps by design: AC-1's workpaper locator waits for P-05-T09's provider (the
  thread opens on a to-do here); AC-8 and AC-15 are P-05-T08's consumer suites; AC-14 conversion
  routes are P-05-T09; AC-29's Sep 14 golden is P-05-T06's bucketing unit test (no demo clock over
  HTTP).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3201 | AC suites run over HTTP on the backfill harness; to-dos are the anchor until T09 | no |
