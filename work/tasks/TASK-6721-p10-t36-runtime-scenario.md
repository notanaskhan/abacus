---
id: TASK-6721
title: "P-10-T36: Brightwater Hale runtime scenario through service APIs (#4127 timeline, run snapshot export, #4118 and #4127 FakeModel trajectories)"
spec: SPEC-647
acceptance_criteria: [AC-W2, AC-W4, AC-W6, AC-W9]
risk_zone: amber
status: in-review
branch: s35-p10-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T36
---

## Objective
make seed-demo loads both runs, the goldens foot, and fixture mode and seed-demo show identical run projections.

## Plan (amber: written before the build)
- `agents/run_recorder.py`: `advance_synthetic_step` (+ `StepAdvance`, exported from `agents.api`):
  a recorded step's later state, the run's state and one `step.state` run event under the
  scenario's business clock, synthetic firms only, as a person of the scenario; audit
  `agent_run.advanced_synthetic` (reviewed fallback).
- `agent_runs_slice.py`: after the 9:41 snapshot, Internal control fails at 9:58
  (`pack_configuration`, written as Marcus Delaney) and Margaret Okonkwo's 11:12 decision
  releases materiality. Loader handler `agents.run_step_advanced` (service API, no SQL).
- `fixture_export.py`: profile `2026-09-14T09:41` (`--slice agent_runs`): the run view and items
  of #4127 as Marcus Delaney.
- `evals/agent_trajectories/suite.yaml`: two FakeModel trajectories (pass cases): #4118 Season
  Progress Reporter (4 reads, 79 open returns, Save to Files waiting) and #4127 Northwind planning.
- Tests: `tests/unit/synthetic/test_p10t36_runtime_scenario.py` (times from the book, handlers,
  profile, trajectories pass), `tests/integration/test_p10t36_run_fixture_equivalence.py`
  (committed export equals seed-demo through the API; projection 1/5/1/4/3, done 1/0/0/0/0);
  P-09-T12's slice test takes the first event and checks the two later ones.
- Rollback: revert; the slice is opt-in.

## Partials (flagged)
- #4118 stays fixture-only (DEC-3121): it is a firm-level run, and the run reads (`runs._run`)
  refuse a run without an engagement until P-10's firm-scope runs. Its figures foot in the book
  and its FakeModel trajectory grades here.
- The plan approval at 9:24 is still the recorder's decided plan (P-09-T12), not
  `commands.approve_plan`: a proposed-then-approved path would change P-09-T12's recorded run
  and its goldens. P-10-T49's journey drives the command path.
- The exported fixture JSON for `2026-09-14T09:41` is generated at the S35 end pass
  (`make fixtures SNAPSHOT=2026-09-14T09:41`, Docker); the equivalence test fails until then.

## Progress log
- 2026-11-10: built; trajectory cases graded (pure code); other tests run at the end pass.
