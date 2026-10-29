---
id: TASK-2012
title: Q-03-T086 Supply-chain hygiene, 2027 Q2
spec: SPEC-341
acceptance_criteria: [AC-47]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T086
branch: s15n-q03-t086
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The quarterly supply-chain cadence and its evidence: findings to SLA, lock refresh and base-image
bumps through their own PRs, and a quarter-end report that fails on anything past its SLA.

## Built
- `supply_chain report --quarter YYYYQn` (per-source seen/closed/open, exit 1 when past SLA at the
  quarter's end) with unit tests (ran once: 15 passed).
- `docs/quality/supply-chain-quarterly.md`: the procedure, today's baseline (every scanner green
  on main; bandit high 0; 2026Q4 report clean) and the Inspector gap with its owner.

## Not done here
- The 2027 Q2 run itself (Jun 30, 2027) and the quarter's lock refresh: an ops cadence, not code.
- Inspector enhanced scanning on the shared registry: the staging stand-up's (it owns `build.yml`
  and the shared account today).

## Progress log
- 2026-10-29: built.
