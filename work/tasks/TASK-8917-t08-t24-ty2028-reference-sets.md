---
id: TASK-8917
title: "T-08-T24: TY2028 reference sets: state holidays, drafts and the review memo"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t08t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T24
---

## Objective
Row: "TY2028 reference sets: federal due-date rules, 2029 federal, DC and pilot-state holidays, 8879 form set and Pub 1345 tolerances, payment-year 2028 information-return thresholds; drafted by import and published under the two-person rule, staging then production by Thu Nov 30, 2028." Acceptance: "The TY2028 sets are published in production with both founders' handles and no deploy, and a TY2028 Form 1040 resolves to Tue Apr 17, 2029."

## Done
- platform reference_sets_contract: LegalHoliday.jurisdiction accepts a state's USPS code (additive)
- practice due_dates: holidays counted per jurisdiction (federal = US + DC; a state = US + its own) across due dates, installments and business days
- abacus_tools.refdata_rollover: pilot-state holidays (CO, IL, NY) with --states
- drafts written outside the repo: refdata-drafts/ty2028/legal_holidays-2028.draft.json and -2029 (SHA-256 in the memo)
- docs/quality/golden-reviews/ty2028-reference-sets@1.md (CPA and counsel review, operator commands for the rolled sets)
- tests/unit/practice/test_t08t24_ty2028_holidays.py (4 pass): TY2028 1040 → Tue Apr 17, 2029; IL → Mon Apr 16; DEC-5919

## Progress log
- `2026-11-23` — Built the code and drafts. Human remainders: the operator writes the due_date_rules, form_8879_set and information_return_thresholds drafts from the published TY2027 sets, the CPA and counsel sign the memo, and both founders publish to staging then production by Thu Nov 30, 2028 (no deploy).
