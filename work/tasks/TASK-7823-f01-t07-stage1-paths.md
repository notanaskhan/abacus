---
id: TASK-7823
title: "F-01-T07 rest: stage 1 runs only the gates a diff can affect"
spec: SPEC-000  # row F-01-T07
acceptance_criteria: [AC-1]  # a frontend-only PR clears required checks in 6 minutes without backend shards
risk_zone: amber  # CI gating
status: in-review
branch: lo39-f01-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: F-01-T07
---

## Objective
Stage 2's path filters already skip backend shards on a frontend-only diff (F-05-T62), but stage 1
ran all of `make check-fast` on every diff: 17.5 minutes on docs-only PR #1801 (DEC-4808).

## Plan
- `Makefile`: `check-fast-frontend` (web and ui tsc, eslint, prettier, the vite build, compiled CSS,
  bundle budget) and `check-docs` (validate_docs, register_ids); `check-fast` calls the frontend
  half, so local `make check-fast` is unchanged.
- `ci.yml` stage 1: classify the diff with `abacus_tools.ci.paths` (stage 2's classifier). Backend
  or unknown paths: `make setup` and `make check-fast`. Frontend-only: `pnpm install`, the
  api-client types, `make check-fast-frontend`, then the docs checks. Prose-only: the docs checks.
- `tests/unit/tools/test_f01t07_stage1_paths.py`.
- Rollback: revert the commit (stage 1 runs everything again).

## Open
- The 6-minute figure is measured on the next frontend-only pull request after merge.

## Progress log
- 2026-11-13: built; the new test and the CI workflow tests pass (71).

## Decisions made during this task
None.
