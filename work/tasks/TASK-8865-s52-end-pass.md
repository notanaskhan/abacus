---
id: TASK-8865
title: "S52: S52 end pass: gates, tests, security review, records"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: done
branch: s52-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: S52
---

## Objective
Run every gate and the S52 tests once, fix what they find, review the red rows, record the sprint.

## Done
- Gates: ruff, pyright 0, lint-imports, banned_patterns, docs, generators, heads, schema_check, frontend tsc/eslint/prettier, vite build, budgets
- Tests: backend unit/contracts/workflows 73.6k, security 17.3k, web changed set 4.6k, kit 1.5k
- Defects fixed (DEC-5861); gate lists (DEC-5862); migration 1002
- Replay histories for the three new workflows
- Dependabot #2136, #1518 folded in

## Progress log
- `2026-11-20` — 2026-11-21: done. Lessons: a whole-tree prettier run rewrites generated files (status.gen.ts) and fixtures; run prettier per package from its own directory. UnitOfWork carries no tenant: providers read in tx.session.
