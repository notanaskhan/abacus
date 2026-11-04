---
id: TASK-3279
title: A-04-T36 independent AC tests for internal control and SOC 1 evaluation
spec: SPEC-000  # row (SPEC-620 AC6, AC7)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T36
branch: s27-a04-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
ADR-078 tests for T25 and T31, written apart from the builds.

## Plan (amber)
- `backend/tests/unit/assurance/test_a04t36_independent.py`: Sheet!Cell derived from the row;
  proposals never write a conclusion; routing 503 before A-06 and inside the unit of work; the
  92-day golden and a Hypothesis bound and stamp-stability property; reliance refused while the gap
  is open; request drafts never sent by code; matrix denies every write to clients, third parties,
  the agent and the system; routes gate before reading.
- No production code changes; rollback is deleting the file.

## Progress log
- 2026-11-04: written; ruff clean; run at the end pass. Third-party room scope (Sam Ortiz sees
  only Keystone requests) is a C5 delegation fact tested by P-04's room tests; here the matrix
  denies `third_party` every A-04 write.
