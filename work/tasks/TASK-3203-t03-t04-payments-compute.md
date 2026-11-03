---
id: TASK-3203
title: T-03-T04 payments compute library, TY2027 parameters and C21 installments
spec: SPEC-643
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T04
branch: s26-t03-t04 (stacked on s26-t03-t03)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"The functions reproduce every TAX-13 figure (110,250; 46,300; 19,990; NY 7,824; 12,733) and the
TY2027 installment dates, and each output carries engine name, version and inputs hash."

## Plan (amber)
- `tax/compute/payments.py`:
  - `safe_harbor`, `paid_by_original_due`, `prior_year_method`, `estate_exempt`,
    `required_annual_payment`, `installment_amounts`;
  - the parameter loader and the stamp.
- `tax/compute/likely_to_extend.py`: `signals(facts, as_of, params)`.
- `tax/compute/parameters/ty2027.yaml`: PROTECTED, a DEC-76 engine parameter file.
- Import-linter: `tax.compute` joins the compute contract. Protected paths and `tax/README.md`
  name the parameter files.
- C21 additive v2:
  - `InstallmentOffset` on `DueDateRuleRow.installments`;
  - `calendar.installment_dates`;
  - `practice.api.installments_for`;
  - `GET /v1/due-dates/installments`;
  - `rules-tables.md`.
- Tests: `tests/unit/tax/test_t03t04_payments.py`.
- Rollback: revert. No migration.

## Progress log
- 2026-11-03: built. The parameter file's `reviewed_by` stays null until the CPA's TY2027 memo
  (T-03-T18). Tests at the S26 end review.

## Decisions made during this task
DEC-2203.
