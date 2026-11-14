---
id: TASK-7836
title: "Main CI after S42: four inherited reds (Today stub, update-column grants, reminders route, report flake)"
spec: SPEC-000  # CI repair
acceptance_criteria: [AC-1]  # the four tests pass on main
risk_zone: green
status: in-review
branch: main-reds-s42
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39-rec
created: 2026-11-14
updated: 2026-11-14
plan_key: F-01-T05
---

## Objective
Main CI 43522183908 (0152ac5d6) and 43508014541 (f84e22721, S42 end pass) failed on tests whose
expectations did not follow S42's merged work, plus one flaky test.

## Delivered
- `tests/contracts/today/test_today_consumer.py`: `POST /v1/me/today/builds` (I-02, 202) is built.
- `tests/integration/test_schema_check_db.py`: `daily_briefings` adds `facts_hash` (0871, I-02-T13).
- `tests/integration/backfill/test_f03t21_binders_request_enum.py`: TXP-10's
  `…/issues/{issue_id}/reminders` (T-05-T51, DEC-4903, `docs/contracts/tax-workbook.md`) joins the
  contracted reminder routes; it is authorised as `follow_up.draft`, so no reminder action exists.
- `tests/unit/quality/test_q03t088_independent.py`: "the report writes nothing inside the
  repository" now records every file the report opens for writing and asserts none is inside the
  repository, instead of comparing a snapshot of the whole repository, which raced other xdist
  workers' files.

## Progress log
- 2026-11-14: built. Today contract suite 35 passed; q03t088 9 passed; ruff and pyright clean. The
  two integration tests were not run here (Docker down); the PR's CI runs them.
