---
id: TASK-3037
title: Q-04-T091 S25 support reserve, AY lane, rehearsed on the synthetic test firm
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # hours are logged at the sprint review and first responses met the SLA, or RK-07 is raised
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T091
branch: s25-q04-t091
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Hours are logged against this row at the sprint review and first responses met the SLA, or the
RK-07 trigger is raised." Run on PF-X1 and reported as synthetic (DEC-1530, DEC-2081).

## Plan (amber)
- `docs/ops/pilot/support-hours.csv`: S25's AY rows (0 hours, no SEV) for Oct 4 and Oct 11, 2027.
- `docs/ops/pilot/desk/s25-ay-lane.md`: the lane's duties, the weekly pilot-metrics read and the
  monthly flag-hygiene report.
- Rollback: revert. Docs only.

## Result
0 hours: no firm reached the desk; RK-07 not raised. The flag-hygiene report finds every one of the
85 flags expiring Apr 21-30, 2027: renew or remove each before the first real go-live.

## Progress log
- 2026-11-03: built; m12_pack's tests read the ledger (10 passed).

## Decisions made during this task
DEC-2081 (TASK-3034).
