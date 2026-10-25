---
id: TASK-1208
title: Gallery axe gate on CI in three shards of two workers (stage 2 run time)
spec: SPEC-045
acceptance_criteria: [AC-9]
risk_zone: green
status: in-progress
epic: F-05
plan_key: F-05 (gallery CI)
branch: s8b-core
created: 2026-10-25
updated: 2026-10-25
---

## Objective
The gallery job ran the axe gate and the screenshot regression on one 4-core runner with four Playwright workers against the vite dev server. On #395 (`s8a-batch`) the page-wide overlay checks took about 3 minutes each, several failed under load (o1-popover parts 1 to 4, forced colours, reduced motion, axe chunk 9) and the 20-minute job limit cancelled the run with about 60 of 98 tests done. All 98 pass locally in 8.5 minutes. Fix the CI shape, not the tests.

## Plan
- Split the job: `gallery` keeps the screenshot regression and parity Tier A and D (name unchanged, 20 minutes); new `gallery-axe` runs the axe gate and harness specs as a matrix of three shards (`--shard=n/3`), two workers each, 25 minutes, one report artifact per shard.
- `stage-2` needs `gallery-axe`. No branch-protection rule names the old check.
- Test: `test_the_gallery_axe_gate_runs_sharded_on_component_library_changes` pins the shape.
- Rollback: revert the commit.

## Progress log
- 2026-10-25: built. `playwright test --list --shard=n/3` gives 33, 53 and 12 tests (`components.spec.ts` is one serial group of 29, so shard 2 is heaviest). CI-shape unit tests: 192 passed. Confirmation is the batch PR's first CI run; if shard 2 still runs long, raise the shard count rather than the timeout.
