---
id: TASK-3033
title: Q-03-T163 integration and conflict lane, 2027 Q3 part 1
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # every red batch run of the period is resolved within one working day and no generated file is hand-merged
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T163
branch: s25-q03-t163
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Every red batch run of the period is resolved within one working day and no generated file is
hand-merged." Measured over the S24 and S25 batches (2026-10-30 to 2026-11-03).

## Plan (red)
- `abacus_tools/ci/integration_lane.py`: count `s<NN>-end-pass` / `-integration` batch branches;
  a push run on a branch other than `main` counts neither way.
- `.github/workflows/ci.yml`: the `visual-change` label makes the screenshot regression report
  instead of fail; fixture journeys run as two shards inside the 15-minute limit.
- `docs/quality/integration-lane-2027-q3.md`: the period's streaks and incidents.
- Tests: `tests/unit/tools/test_integration_lane.py` (two cases), `test_journey_workflows.py`.
- Rollback: revert. No migration, no flag.

## Result
Not met: `main` has had no green `ci` run since 2026-10-30 (29 failed, 19 cancelled), and the S24
and S25 batches merged with CI skipped on the owner's decision. The streak closes with one green
`ci` run on `main`'s head. No generated file was hand-merged (the S25 batch regenerated the client
and statuses in #1106).

## Progress log
- 2026-11-03: built. Lane tests 8 passed; workflow tests 4 passed; the shards list 106 and 85 of 191
  journeys.

## Decisions made during this task
DEC-2080.
