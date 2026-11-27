---
id: TASK-9032
title: "T-08-T31: TAX-14 firm standards run A-E on T1"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-t08-t31-tax14
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-08-T31
---

## Objective
TAX-14 A-E on T1: standard chip and picker, filter chips and tiles, checkbox table with shift-range select, per-row progress, expanded check list with links to TXP-10 and TXP-07, Open exceptions, Run on selection, toast and empty state.

## Done
- TAX-14 A-E render from data
- The run updates live
- Run on selection re-runs only the checked rows
- Run read gains row facts, version and check words (Postgres test; untyped-param 500 fixed)
- Fixture from the Python scenario

## Progress log
- `2026-11-27` — 2026-11-27: built per DEC-6037. The Postgres test found every standards run read answering 500 on untyped params. It is fixed and covered by test_t08t31_standard_run_rows. 9 TAX-14 tests green. KNW-01 links to TAX-14. Noted a pre-existing isolation failure in test_t08t14 (it passes in the suite).
