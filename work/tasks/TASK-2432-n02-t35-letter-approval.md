---
id: TASK-2432
title: N-02-T35 ENG-04 approval dialog, consent rule, envelope withdrawal and independent suite
spec: SPEC-381
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-02
plan_key: N-02-T35
branch: n02-t35-letter-approval-dialog
worktree: /Users/ayushkbhatia/Accrued/abacus-s19b5
created: 2026-10-31
updated: 2026-10-31
---

## Objective
ENG-04's approval dialog with step-up and consent rows, the withdrawal path for a declined or
expired letter envelope (DEC-1468's "Not here"), and the ADR-078 independent suite for T32-T33.

Acceptance: "The suite passes and fails if a manager's approval or a consent clause inside the
letter is accepted."

## Plan (amber)
- Migration 0567 (on 0566): the letter guard allows `sent` → `partner_approved` only with the
  envelope cleared, by a person.
- `letter_flow.withdraw_envelope`, the envelope-status port, `ConsentInLetter` in `letters`.
- ENG-04: Approve letter… dialog (consents, step-up), Withdraw envelope… confirm.
- Tests: `tests/integration/test_n02t35_letter_independent.py` (end review).
- Rollback: downgrade 0567; revert.

## Progress log
- `2026-10-31` — Built on `n02-t35-letter-approval-dialog`, stacked on #937 for 0566. DEC-1480.
