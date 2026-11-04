---
id: TASK-3280
title: A-05-T37 independent AC tests and goldens for contributions and late remittances
spec: SPEC-000  # row (SPEC-640 F6)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T37
branch: s27-a05-t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
ADR-078 tests for the contributions engines and the late-remittance service.

## Plan (amber)
- `backend/tests/unit/assurance/test_a05t37_independent.py`: 9 business days and the Dec 30 due
  date; the small-plan safe harbor never for a large plan; VFCP 64.38 and excise 9.66 golden; a
  missing rate refuses; Hypothesis idempotence, non-negativity and monotonicity; line 4a from
  deferrals only; the correction state machine (evidence, human event, pending until the SCC
  notice, never by clock, once); Form 5330's recordable words; one object for every consumer.
- No production changes; rollback is deleting the file.

## Progress log
- 2026-11-04: written; ruff clean; run at the end pass.
