---
id: TASK-3282
title: A-06-T20 independent AC tests for findings, decision kinds and the SUM service
spec: SPEC-000  # row (SPEC-642 F1, F2, F4)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T20
branch: s27-a06-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
ADR-078 tests: INV-1, reserved role, rationale and MFA, INV-2, INV-3, INV-5, snapshot immutability.

## Plan (amber)
- `backend/tests/unit/assurance/test_a06t20_independent.py`: matrix denies the agent and the system
  every finding closure and decision request; both decision kinds reserved to the engagement
  partner; `decision.decide` needs fresh MFA; an agent finding needs verified citations and Why
  This Was Surfaced states only code's figures; routes gate first; the agent-raised row reads
  "<person> via Agent"; `sum_snapshots` insert-only.
- No production changes; rollback is deleting the file.

## Progress log
- 2026-11-04: written; ruff clean; run at the end pass. Expected to surface: `findings._rows`
  writes "Accrued Agent" without the person (INV-5); the fix belongs to the end review's round.
