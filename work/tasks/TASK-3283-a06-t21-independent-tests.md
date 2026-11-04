---
id: TASK-3283
title: A-06-T21 independent AC tests for G5, the review extensions and the agent seams
spec: SPEC-000  # row (SPEC-642 F5)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T21
branch: s27-a06-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
ADR-078 tests: I-GATES G5 rows, staleness reopens G5, reopen blocks again, only a human clears, EQR
L5 column read-only, suggestion appliers human-only.

## Plan (amber)
- `backend/tests/unit/assurance/test_a06t21_independent.py`: G5 over stubbed review reads: met when
  signed and fresh; a stale level reopens it; an open note blocks; unsigned and no reviewables stay
  unmet; a failing provider is unmet; the matrix denies the agent clearing, signing and resolving a
  suggestion; the sign-off matrix is GET only with no action on a cell.
- No production changes; rollback is deleting the file.

## Progress log
- 2026-11-04: written; ruff clean; run at the end pass.
