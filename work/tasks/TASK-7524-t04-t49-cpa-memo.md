---
id: TASK-7524
title: T-04-T49 tax CPA golden review memo for the individual return engines
plan_key: T-04-T49
spec: SPEC-649  # T-04 §4.4; chapter 10 §10.9.4
acceptance_criteria: [AC-1]  # the memo is signed before May 2; make entitlement refuses the module for a non-synthetic firm without it
risk_zone: amber
status: in-review
branch: t04-t49-golden-memo
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
`docs/quality/golden-reviews/tax-individual@v1.md` for the T-04 engines (case-list hash, TY2025 and
TY2027 parameters, exceptions), the signature record, `requires_review` on each engine, and the
entitlement refusal while unsigned.

## Plan
- The memo (EBP pattern): engines, goldens with figures, tests, reviewer ticks, exceptions.
- `tax/compute/individual/parameters/review.yaml` (PROTECTED, `signed: false`) and
  `tax/compute/individual/review.py` (`review_signed`, `ENGINES`); exported on `tax.api` as
  `individual_review_signed`.
- `abacus_tools/tenants.set_entitlement` (`make entitlement`): enabling `tax_returns` for a firm
  that isn't synthetic is refused while the memo is unsigned (DEC-4524). The runtime is not
  gated: T-01 to T-03's Tax Returns surfaces predate this review.
- Test `tests/unit/tax/test_t04t49_cpa_review.py` (case-list hash, engines, status agreement, the
  refusal).

## Partial
- The CPA's signature (human, the vault reference) and `reviewed_by` in `ty2025.yaml`.

## Progress log
- `2026-11-12` — Memo and record written (DEC-4524). Tests run at the S39 end pass.
