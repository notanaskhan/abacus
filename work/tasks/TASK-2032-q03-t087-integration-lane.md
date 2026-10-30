---
id: TASK-2032
title: Q-03-T087 Integration and conflict lane 2027 Q2 (part 2 of 2)
spec: SPEC-341
acceptance_criteria: [AC-52]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T087
branch: s15c-q03-t087
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Batch-branch failures, hot-file and regenerated-file conflicts, migration renumbering and cut-over
defects across epics; every red batch run of the period resolved within one working day, no
generated file hand-merged.

## Plan (red: written before the code)
- `abacus_tools.ci.integration_lane`: red streaks on `main` and batch branches from `gh run list
  --json`, working-day age to the next green, exit 1 on a breach.
- `abacus_tools.quality.register_ids` in check-fast: a decision, escaped-defect or runbook ID twice
  fails (the merge damage the S15 group B batch left, which nothing caught).
- Fix the damage on `main`: DEC-1053 and DEC-1058 to DEC-1061 twice (S15 group B), DEC-1157 in two
  versions (S16 T-01: the stacked revision kept, the original removed).
- `docs/quality/integration-lane-2027-q2.md`: the lane's rules (regenerate, never hand-merge; one
  migration head; one row per ID; diff the batch tree before the CI-running merge; one working day)
  and the period log with the measured streaks and the incidents.
- SPEC-341 AC-52; tests `unit/tools/test_integration_lane.py`, `unit/quality/test_register_ids.py`
  (run at the end review).
- Part 1 (Q-03-T076, S14) and the Q1 lane (Q-03-T020) were never built; this task carries both
  tools, so the rules apply from now.

## Measured 2026-10-30
One past breach (Oct 26 to Oct 29, 2.43 working days, before this lane). An open streak from
`c441d80c` (Oct 29): every later `main` run was cancelled as superseded; `64e465ef`'s run decides it.

## Progress log
- 2026-10-30: tools, register fixes, lane log, AC and tests built.
