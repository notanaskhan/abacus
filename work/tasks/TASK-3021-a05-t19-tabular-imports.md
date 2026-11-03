---
id: TASK-3021
title: A-05-T19 tabular source imports
spec: SPEC-640
acceptance_criteria: [AC-17]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T19
branch: s25-a05-t19 (stacked on s25-a05-t18)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"The Northwind census imports 301 participants with SSNs sealed, and a register whose total does
not foot is refused with the difference shown."

## Plan (amber)
- `assurance/ebp_imports.py`: kinds census, payroll register, loan report, account balances,
  SDBA detail, trust receipts; parse by the person's column map from evidence's isolated
  extraction; footing to a total row or a keyed control total; census ties to the latest PayGrid
  register and W-3 Box 1 + Box 12 D; sealed participant writes through A-05-T18's `seal_pii`;
  refusals recorded (`status = refused`).
- Contract: `ImportIn` kinds follow M2's CHECK (the stub's `hr`, `payroll`, `w3` were never DB
  kinds); `ImportOut`; GET `/ebp/imports/{id}`; participants served from the latest census.
  `ParticipantOut.ssn` is optional (a census row may carry no SSN).
- No migration. Rollback: revert the PR.
- Tests: `tests/unit/assurance/test_a05t19_imports.py` (18),
  `tests/integration/backfill/test_a05t19_imports_db.py`.

## Progress log
- 2026-11-02: built; unit tests pass, the DB file runs in the end pass. Not built: the
  `phi_not_permitted` refusal (F3; RK-35) waits for P-03's scan to flag census rows; HR roster,
  vendor and customer masters (T21, AUD-27) import later. Client regeneration in the end pass.

## Decisions made during this task
DEC-2068.
