---
id: TASK-3035
title: Q-04-T085 deadline week Oct 11-15 watch, rehearsed on the synthetic test firm
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # no release or flip ran in the week and every daily check is logged
risk_zone: red
status: done
epic: Q-04
plan_key: Q-04-T085
branch: s25-q04-t085
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"No release or flip ran in the week and every daily check is logged." Run on PF-X1 and reported as
synthetic (DEC-1530, DEC-2081).

## Plan (red)
- `docs/ops/windows/2027-10-11-deadline-week-watch.md`: the gate at 09:00 and 19:05 CT each day
  (`abacus_tools.window_rehearsal`, from TASK-3034), the rota check, and RB-16's daily checks.
- Tests: T084's `test_t085_every_day_of_the_oct_11_to_15_week_refuses_a_promotion_without_a_hotfix`.
- Rollback: revert. Docs only.

## Result
No release or flip could run: every day refuses a promotion without a hotfix and none is a flip
slot; no flip is planned. The rota covers every day on double cover. The canary, SES and provider
checks need production and are logged as not run.

## Progress log
- 2026-11-03: built.

## Decisions made during this task
DEC-2081 (TASK-3034).
