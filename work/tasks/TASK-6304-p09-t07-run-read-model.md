---
id: TASK-6304
title: P-09-T07 run read model, v2 header, projection by level, items feed, synthetic recorder
spec: SPEC-648
acceptance_criteria: [AC-1]  # #4127 1/0/0/0/0 of 1/5/1/4/3; legacy screener one tool card; walled 404
risk_zone: red
status: done
epic: P-09
plan_key: P-09-T07
branch: s32-p09-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
Finish the run view and feed TASK-5000/5001 started: v2 header, code-computed projection by
level, v2 items, active list, and the synthetic-only recorder P-10 lacks.

## Plan
- New `agents/run_views.py`: `v2_facts`, `project`, `levels_for`, `v2_items`, `item_of`.
- `agents/runs.py`: `RunHeader`, `RunView.header/levels`, `RUN_ACTIONS` passthrough, v2 feed
  (`_v2_run_items`, metadata filtering), active list by v2 state.
- `agents/runs_routes.py`: header and levels on `RunViewOut`; `RunItemOut.kind` widened
  (additive); blocks re-validated.
- New `agents/run_recorder.py` (synthetic firms only).
- Contract §11; DEC-3004. No migration, no flag change (routes already behind
  `agent_run.read`; the dock is behind `agent_dock.enabled` on the client).
- Tests: `tests/unit/agents/test_p09t07_run_projection.py`,
  `tests/integration/agent_tests/test_p09t07_run_read_model.py`.
- Rollback: revert.

## Progress log
- `2026-11-09` — Built; ruff and pyright clean on touched files; tests written, not run (S32 end
  pass). `packages/api-client` regenerates at the end pass (`RunItemOut.kind` enum widened).
  The run row's `started_at` is server-set, so the recorder can't backdate a run to 9:24; steps
  carry their own times. P-09-T12 reads the demo clock for the run start.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3004 | Step-state buckets, v2-run detection, metadata filtering of v2 items, the recorder's scope | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
