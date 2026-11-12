---
id: TASK-7523
title: Q-03-T259 CL-1 independent equivalence tests
plan_key: Q-03-T259
spec: SPEC-650  # P-05 §2.3 CL-1
acceptance_criteria: [AC-1]  # the equivalence suite passes on a copy of the canary's threads
risk_zone: amber
status: in-review
branch: q03-t259-cl1-equivalence
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The independent equivalence suite for CL-1, written before the consolidation.

## Plan
- `backend/tests/contracts/collaboration_cl1/test_cl1_equivalence.py`: the window's guards
  (`LIVE_SPEC032_KINDS`, `requests` owning the four tables) asserted; ownership, anchor kinds,
  identical reads with no row updated in place, and `comment.mentioned` retired as strict xfails
  naming Q-03-T258 (DEC-4522).

## Partial
- Passing "on a copy of the canary's threads" needs CL-1 and the canary (P-05-T16).

## Progress log
- `2026-11-12` — Suite written. It runs at the S39 end pass.
