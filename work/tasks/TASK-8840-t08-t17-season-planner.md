---
id: TASK-8840
title: "T-08-T17: engagements.season_planner capability"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-t08t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-08-T17
---

## Objective
The planner proposes the two-binder ask and reassignments only to eligible staff, writes nothing, and a TRI-tagged input is refused by the gateway.

## Done
- spec yaml + _specs_v2 regenerated
- prompt engagements.season_planner@v1
- engagements/season_planner.py (code asks, eligible pool, settle, plan, answer)
- build route runs planner, asks read model, answer route live
- start_capability_run engagement optional
- activity_reviewed
- tests/unit/engagements/test_t08t17_season_planner.py
- DEC-5842

## Progress log
- `2026-11-20` — Plan (red): spec, prompt, module, route wiring, tests; no migration (0960); rollback = revert. Tests at the end pass.
