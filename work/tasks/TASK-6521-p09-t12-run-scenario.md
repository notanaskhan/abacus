---
id: TASK-6521
title: "P-09-T12: Brightwater Hale run scenario through the agents recording service"
spec: SPEC-648
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-review
branch: s33-p09-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-09-T12
---

## Objective
Footing tests prove 2,625, 79 = 10 + 26 + 26 + 17, 14 = 1 + 5 + 1 + 4 + 3 and 73,166.90 − 1,684.54 =
71,482.36, and fixture mode equals the seeded tenant.

## Plan (amber)
1. `tests/golden/scenario/brightwater_hale/agent_runs_figures.json`: the four E0 runs' figures,
   verbatim from P-09-T01's fixtures (the WB-09 and SHL-13 handoffs).
2. `agent_runs_slice.py` (`--slice agent_runs`, after `audit_core`): #4127 at the 9:41 snapshot,
   14 steps over 5 levels, recorded by `loader._run_recorded` through `agents.api
   .record_synthetic_run` as Marcus Delaney (synthetic firm only; `NotSynthetic` elsewhere).
3. `tests/unit/synthetic/test_p09t12_agent_runs_figures.py`: the four footings and the slice.
Rollback: revert; the slice is opt-in.

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). Partial: #4118 and the Aug 17 run are
  firm-level (a run row needs an engagement until P-10's firm-scope runs), Copperleaf Run 2 needs
  C-01's close engagement, and #4119 has no data in the handoff or the fixtures; these stay
  fixture-only. `make fixtures` export is unchanged (the fixtures already hold the runs).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3121 | Which runs seed now and which stay fixture-only | no |
