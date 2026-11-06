---
id: TASK-3385
title: CI job limits for the combined S27 and S28 run
spec: SPEC-000  # row (none)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s28-ci-limits
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Ayush asked to raise the three limits and run one full CI on the landed S27 and S28 work.

## Plan
- `.github/workflows/ci.yml` limits; a touch on a gallery, an SPA and an agents path so the path filter starts every job. Rollback: revert.

## Progress log
- 2026-11-06: limits raised. See DEC-2384.

## Decisions made during this task
DEC-2384
