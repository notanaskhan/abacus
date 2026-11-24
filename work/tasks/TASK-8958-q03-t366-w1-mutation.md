---
id: TASK-8958
title: "Q-03-T366: Quarterly mutation sweep: N's red modules (posting, write capabilities)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-mutation-sweeps
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-24
updated: 2026-11-24
plan_key: Q-03-T366
---

## Objective
No red module is below its floor.

## Done
- mutation-weekly collected nothing since Nov 22: xdist_group registered (ED-330, in TASK-8953)
- w1/posting scope (DEC-5943): posting, recovery, workflow, writes, capabilities, w1_switches, the QBO writer; mutation and coverage floors
- local run 4,223 mutants: 7.3% (308 killed, 3,504 with no container-free test); floor 7, target 75

## Progress log
- `2026-11-24` — 2026-11-24: met for the new scope; the other scopes' floors are mutation-weekly's on main (it collects again). Raising w1/posting needs unit tests over its pure parts.
