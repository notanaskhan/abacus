---
id: TASK-6016
title: "A-06-T32 the Findings tab badge is the findings awaiting a decision (3), asserted from both sides"
spec: SPEC-000  # row (A-06-T32)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T32
branch: s29m-a06-t32-badge
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-06-T32 left AUD-15's tab badge unasserted (no fixture field). Tracing it found a real bug: the Evaluation tab drew the list total (9) where the handoff draws 3, and the backend's awaiting count left out the exception still to resolve.

## Plan
assurance/findings.py: AWAITING_DECISION (proposed, exception_for_resolution) and awaiting_decision(), used by findings_of. EvaluationPage: the Findings tab count reads counts.awaiting_decision. Fixtures: aud15List and the audits handler serve the count. Tests: backend golden badge check, web figure-book badge check, evaluation tab test reads Findings 3. Rollback: revert.

## Progress log
- 2026-11-08: built. Backend test_a06t32 8 passed + 1 strict xfail; web evaluation, AUD-15 and completion-figures 34 passed + 1 expected fail; tsc, eslint, prettier, ruff, pyright clean.

## Decisions made during this task
DEC-2612
