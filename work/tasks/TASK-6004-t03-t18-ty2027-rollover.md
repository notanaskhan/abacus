---
id: TASK-6004
title: "T-03-T18 TY2027 rollover: draft tool, RB-62, review memo, load profile"
spec: SPEC-000  # row (T-03-T18)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T18
branch: s29l-t03-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
On Fri Dec 10, 2027 (M15) production resolves TY2027 due dates from published rows carrying both handles and every pilot firm has a published TY2027 organizer, with no rule content in any commit except the DEC-76 parameter file.

## Plan
abacus_tools/refdata_rollover.py: drafts the season's reference sets outside the repo (refuses inside): rolls due_date_rules (unchanged offsets), form_8879_set (tax_year moved, tolerances carried for re-verification, DEC-85) and information_return_thresholds (payment_year moved) from the version in effect, and computes legal_holidays from 5 U.S.C. 6103 and D.C. Code 1-612.02 at observed dates; each draft carries a review block. refdata.current_payload (public reader; _current_rows uses it). RB-62 tax-year rollover (draft, review, two-person publish staging then production, organizers, flip and rollback), runbooks index; RB-16 R4-16; docs/quality/golden-reviews/ty2027-reference-sets@1.md (CPA and counsel, awaiting; the 2028 holiday draft's hash recorded); load profile tax_season_lists. The T-03 flag retirement is its own held PR. Rollback: revert; nothing is published by code.

## Progress log
- 2026-11-07: built. tests/unit/tools/test_t03t18_rollover.py passes (6): 2028 holidays exact with observed dates, inauguration rule, weekend rule, rolled years, refusals, no draft inside the repo. The 2028 holiday draft written to the ops folder. Not done: the TY2026 versions to roll from (staging and production publish them), the CPA and counsel review, the two-person publishes, pilot organizers (no live firm), the December load test.

## Decisions made during this task
DEC-2604
