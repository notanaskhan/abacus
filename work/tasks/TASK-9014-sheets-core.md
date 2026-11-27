---
id: TASK-9014
title: "K-03-T20: Sheets core service"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-k03-t20-sheets-core
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: K-03-T20
---

## Objective
Row acceptance: A sheet is created empty when its procedure moves to in progress, 40 rows arrive from sample seed 0x7C31B4 with totals 3,286,400.00 and 412,300.00, a stale row version answers 412, and no cell is written outside record_value.

## Done
- create from the linked version's definition
- rows from the approved sample in strata sections with code's totals
- manual rows and cell edits through record_value with row version (412) and lock (409)
- stored views with code filters and sort
- row links service
- Postgres acceptance test

## Progress log
- `2026-11-26` — Built; acceptance passes on Postgres (81 cells, each with a field_value_versions row). The procedure-start event arrives with K-04; the create route is the same service.
