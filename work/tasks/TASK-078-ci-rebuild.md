---
id: TASK-078
title: CI rebuild — stage 2 on main and the merge queue, ready-for-review gating, generated-file and single-head checks, vite build (epic F-01-T06)
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: red
status: done
branch: task-078-ci-rebuild
worktree:
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Every commit on `main` gets the full stage 1 and 2 run, drafts get stage 1 only, and stage 1 catches hand-edited generated files, split migration heads and a broken frontend build (epic F-01-T06).

## Scope
**In**
- `.github/workflows/ci.yml`: stage 2 on push to `main`, `merge_group`, and non-draft PRs (`ready_for_review` added); per-commit runs on `main` are never cancelled; uv cache; stage 3's diff base for pushes and the merge queue.
- `Makefile`: `check-generated` (all five generators, naming the one to run), `check-heads` (one Alembic head), `vite build` in `check-fast`.

**Out**
- Required status checks in the ruleset (phase 2): the founder pushes straight to `main` (2026-10-19), and a required check would reject those pushes.
- Re-recording `durations.json` shards (needs a full timing run; follow-up).
- Path filters and the frontend job (F-01-T07).
- pnpm and Playwright caches (pnpm is enabled through corepack after `setup-node`, so its cache can't be keyed there).

## Plan
Approved by founder (2026-10-19, auto mode: "create approval files and then proceed to task"): paths `.github/workflows/ci.yml`, `Makefile`; approval file `work/approvals/TASK-078.yaml`, expires 2026-10-26.

## Definition of done
- [x] `make check-generated check-heads` pass locally; `alembic heads` works without environment settings.
- [x] `make check-fast` passes locally.
- [ ] CI on the PR: stage 1 green with the new steps; stage 2 runs.
- [ ] After merge: the push to `main` runs stage 2.

## Progress log
- 2026-10-19: Makefile and workflow changed; local checks green.

## Gotchas and discoveries
- Coverage is 73% against the 95 floor (TASK-077), so every `main` run's `coverage` and `stages 1 and 2` jobs stay red until back-fill or the governance ADR's dated exception (DEC-10).

## Questions for the human
- None.

## Handoff
Waiting on CI for the PR, then merge to `main` and confirm the push run includes stage 2. Delete `work/approvals/TASK-078.yaml` after merge.
