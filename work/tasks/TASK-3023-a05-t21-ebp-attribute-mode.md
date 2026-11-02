---
id: TASK-3023
title: A-05-T21 mode ebp_attribute
spec: SPEC-641
acceptance_criteria: [AC-F4]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T21
branch: s25-a05-t21 (stacked on s25-a05-t16)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"Row 22's hire-date difference is marked Needs human with a computed no-effect note, and no model
input contains an unmasked SSN or DOB."

## Plan (red)
- `assurance/ebp_attribute.py`: `compare` (census against the HR roster by code: SSN and DOB on
  fingerprints, name and hire date on values; hire-date differences carry the eligibility
  engine's note, the census DOB opened by code only); `check_facts`; `assert_masked` (fail closed
  on an SSN pattern or a participant's DOB in any model input); `attribute_inputs` (the mode
  mapping: HR and payroll records as masked documents, code's results as facts).
- A-05-T19's import gains the `hr_roster` kind (sealed like the census).
- Prompt `workpapers.section_draft.ebp_attribute@v1`; spec v7; agent specs and eval suites
  regenerated.
- No migration. Rollback: revert the PR (spec v6 returns).
- Tests: `tests/unit/assurance/test_a05t21_attribute_mode.py` (10).

## Progress log
- 2026-11-02: built; unit tests pass. The grid that shows the results and takes a person's marks
  is A-05-T22 (S26); the synthetic Northwind HR file has no differences, so row 22's case is a
  unit fixture until T25's goldens.

## Decisions made during this task
DEC-2070.
