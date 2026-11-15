---
id: TASK-8056
title: "A-09-T06: consumer contract tests for the A-09 stubs (pytest + TypeScript fixtures)"
spec: SPEC-658
acceptance_criteria: [AC-0.5]
risk_zone: amber
status: in-review
branch: a09-t06-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T06
---

## Objective
Consumer suites that fail when a provider renames a field or a seed total stops footing.

## Plan
1. `backend/tests/contracts/c09_consolidation/test_consolidation_stub.py`,
   `backend/tests/contracts/group_audit/test_group_audit_stub.py`.
2. `apps/web/src/fixtures/seed/group-audit.ts` (typed seed) and
   `fixtures/contracts/group-audit-figures.test.ts`.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Written (DEC-5041). ruff, pyright, tsc, eslint clean. Run at the end pass.
