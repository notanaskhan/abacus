---
id: TASK-2621
title: T-01-T49 independent AC tests for T-01-T35, T36, T37 and T43 with the I-8879-DRIFT goldens
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T49
branch: s21-t01-t49
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"The suite passes on main from the contract and SPEC alone, and the goldens carry the tax CPA's
and counsel's sign-off references." (ADR-078; I-8879-DRIFT; DEC-85.)

## Scope
- `backend/tests/golden/tax/i8879_drift/cases.yaml`: eleven synthetic cases (exactly 50 and 14
  hold; 50.01, 51, 14.01 and 15 relock; NY only; a refund turning into a balance due; a
  jurisdiction appearing), with `signed_off: {tax_cpa, counsel}` references (pending, human).
- `backend/tests/unit/tax/test_t01t49_drift_independent.py`: every golden through `filing.drift`;
  a wider tolerance holds the same move (relock only from the rows' values); the tolerances are
  C21's `form_8879_set` rows for the year and a year no row covers is `LookupError`.
- `backend/tests/integration/test_t01t49_filing_independent.py`: DEC-38 (a senior or staff member
  never approves the packet; assembly asks no model); a withdrawn ERO designation refuses the
  transmission; a transmitted return takes no second record.
**Covered by the implementing suites, not repeated (DEC-1668)**: ack import idempotence and the
accepted move (T-01-T37), fresh MFA on the ERO designation (T-01-T37), the system-only relock
(T-01-T36), the sealed CAF and the profile's refusals (T-01-T43). **Human**: the tax CPA and
counsel record their TY2026 sign-off on the goldens; the references move from "pending".

## Progress log
- 2026-11-01: written; runs at the batch's end review.
