---
id: TASK-2320
title: T-01-T23 scenario slice, part 1 (the §7216 consents)
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: T-01
plan_key: T-01-T23
branch: s18-t01-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Brightwater Hale's T-01 content through the scenario loader. Part 1: ADM-05's 218 consents.

## Plan
- `brightwater_hale/consents_7216.py` (data, footing, slice) and the loader's
  `organisations.consent_recorded` handler; NEEDS `binders`.
- Test: `tests/unit/scenarios/test_t01t23_consents_slice.py`.
- DEC-1366 lists the parts that wait on tables not yet on main.

## Progress log
- `2026-10-30` — part 1 built; footing tests run once (5 pass). The load itself runs in the S18
  end review (`make seed-demo SLICE=consents_7216` against a local database). `[skip ci]`.

## Handoff
- **Current state:** part 1 built, PR open; parts 2+ follow their tables (DEC-1366).
- **Exact next step:** T-01-T24 (TAX-12 frontend part 1).
