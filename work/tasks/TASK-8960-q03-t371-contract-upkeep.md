---
id: TASK-8960
title: "Q-03-T371: Contract-test upkeep 2028 Q4 (N-provided contracts)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-quarterly-sweeps
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-24
updated: 2026-11-24
plan_key: Q-03-T371
---

## Objective
Every consumer suite green in provider CI and the drift count zero at the quarter's end.

## Done
- abacus_tools.contracts --check passes
- consumer suites 10,824 green after the CI repair (TASK-8953)
- fixture-versus-live drift 0 (KNOWN_DRIFT empty); ED-270 closed
- no openapi-compat exception, no vN+1 overlap due

## Progress log
- `2026-11-24` — 2026-11-24: met; provider CI is the batch tip's run.
