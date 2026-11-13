---
id: TASK-5307
title: A-05-T16 EBP-03 rates, EBP-04 expected figures and EBP-09's expenses clause read verified provisions
spec: SPEC-640
acceptance_criteria: [AC-14]  # F2: the downstream readers read the verified values only
risk_zone: amber
status: done
epic: A-05
plan_key: A-05-T16
branch: s25d-a05-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s25d
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-05 F2: "EBP-03's header cards, EBP-04's match formula and EBP-09's expenses clause read the
**verified** values; an unverified agent value is never consumed downstream." DEC-2482 did EBP-03's
entry rule; this does the rest.

## Plan (amber)
- `compute/ebp/eligibility.py`: `Rates`, `rates_from`, `match_pct_from`; `missed` takes the match rate.
- `compute/ebp/expenses.py`: `plan_may_pay`.
- `ebp_provisions.py`: `RatesRead`, `ExpensesClauseRead`, `PlanReads`, `plan_reads`.
- EBP-03 (`ebp_eligibility_sample.py`), EBP-04 (`ebp_tests.py`), EBP-09 (`ebp_contract.py` route).
- Contract (additive): `RatesOut`, `EligibilitySampleOut.rates`, `ExpensesClauseOut`,
  `ExpensesOut.expenses_clause`, `ExpenseRowOut.not_permitted`. Client regenerated.
- Rollback: revert. No migration.

## Tests
`tests/unit/assurance/test_a05t16_plan_reads.py`; `test_a05t23_eligibility_sample.py` (unit and
trust kit, a case with unverified rates); `test_s27p_ebp04.py`.

## Progress log
- 2026-11-08: built. EBP-04's grid with unverified rates is covered by reading the guard, not by a
  test: `contribution_recalc` reads the database in several places a unit test would stub.

## Decisions made during this task
DEC-2488.
