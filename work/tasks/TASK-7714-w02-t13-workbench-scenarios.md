---
id: TASK-7714
title: W-02-T13 Brightwater Hale Workbench scenarios and fixture export
plan_key: W-02-T13
spec: SPEC-653
acceptance_criteria: [AC-L1, AC-L2, AC-V1]
risk_zone: amber
status: in-review
branch: w02-t13-workbench-scenarios
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
WB-01's eight rows and the three close runs in the database through service APIs, matching the
fixture, so `seed-demo` and fixture mode answer the same list.

## Built
- `workbench/session_seed.py` (synthetic-only recorder), `workbench/api.py` exports,
  `workbench_slice.py` (11 sessions), loader handler; `identity/colleagues.py` and W-02-T09's
  membership completed per DEC-4601 Q1.
- Tests: `backend/tests/unit/workbench/test_w02t13_workbench_slice.py` (cross-checks the TS
  fixture's titles and ids).

## Partial
- The J11 run's thread (plan, two questions, gathering/working/ready, the workbook artifact, the
  approved save and the variants) is P-10's `j11-adhoc-session` extension: not seeded here; row
  1 carries its first message only.
- `make fixtures` export of the list and the equivalence test (F-04-T31's mechanism) are not
  extended to workbench reads; the slice mirrors the fixture by id and title instead.
- WB-02's Northwind context scenario (2:40 PM answer) is not seeded. S41 leftovers scan
  (TASK-7733): a 2:40 PM session would join Hannah's WB-01 list, which E0 pins at eight 9:24 AM
  rows (the slice loads every session), and the answer needs P-10's turn recorder and the PayGrid
  and Keystone documents; it needs a per-scenario variant in the loader.

## Progress log
- 2026-11-13: built; slice smoke-imported (12 events); tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4717 | the recorder, the slice and DEC-4601 Q1 colleagues | no |
