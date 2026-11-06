---
id: TASK-5015
title: A-05-T23 remainder - EBP-03's sample service, Raise exception and Request opt-out forms
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T23
branch: s26r-a05-t23-ebp03-sample
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-06
updated: 2026-11-06
---

# TASK-5015 · A-05-T23: EBP-03 on live data

TASK-3235 built the screen on fixtures and left the route at 501.

AC-1: `GET …/ebp/eligibility/sample` returns the test's rows in A-03's order, census against HR,
with code's entry date, the row's result and code's missed amounts on an exception.

AC-2: no response discloses a date of birth: `dob_masked` is constant, and `eligible_on` appears only
where hire + 3 months governs. No test yet is no rows, and the screen's empty state.

AC-3: Raise exception… records an AUD-15 draft finding; Request opt-out forms opens SHL-14.

## Decisions (DEC-2328)
- `test_id` and `census_hire` became nullable: a work item with no test, or a sampled key not on the
  census, is shown and never dropped.
- The rate label is code's: the census election, or the escalated default when it has none.

## Known limits
- `hr_record_version_id` and `recordkeeper_entry_on` come from the agent's cell value, so they are
  empty until `ebp_attribute` writes them there.
- Masked SSN with Reveal lives in the evidence viewer's HR record and is not drawn here.
- The provision cards are not repeated on this screen.
- Raise exception records one finding for the sample's exceptions and stays disabled for that page
  view; a reload can raise another.

## Progress log
- 2026-11-06: built on main 49922a2fd.
