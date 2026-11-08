---
id: TASK-3401
title: A-06-T24 Northwind's sign-off matrix holds AUD-17's 26 rows and footer
spec: SPEC-000  # row (A-06-T24)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T24
branch: s28p-matrix-26
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Part 3 of AUD-17's 26 rows (Ayush, 2026-11-08: all 26, the undrawn rows' cells made up). Northwind's live matrix had 10 rows; the handoff counts 26 = 6 + 3 + 7 + 6 + 4 with Prepared 25, Reviewed 24, Partner 8 of 13, EQR 0 of 6 and one changed after sign-off.

## Plan
- Completion slice: the firm's review_levels version with each row kind's levels (published Sep 28, after E0 and SHL-12), 14 papers through `workpapers`, SHL-12's two trial-balance notes cleared, and the sign-offs, all through the services.
- `review_matrix.matrix` keys facts and sign-offs by type and id.
- Golden figures and the web fixture move to 26 rows; S29's strict expected failures become plain checks.
- End-pass fixes for the stack: SQL-001 in part 2's statements, the reopen route in the app-gates pin.
- Rollback: revert; the seed's levels version only affects synthetic Brightwater Hale.

## Progress log
- 2026-11-08: built. `tests/integration/test_a06t28_completion_load.py` (new: 26 rows by group, the footer, three drawn rows' cells) with `test_a06t16_checklist_suggestions.py`: 14 pass on Postgres; `test_a06t28_checklist_load.py` and `test_g02t22_ai_policy_ac_suite.py`: 169 pass; golden `test_a06t32_completion_figures.py` 9 pass; web completion-figures and AUD-17: 17 pass. Unit suite 42,771 pass; 8 fail, none from this stack after its fixes: `test_classification` (local libgobject), and three of main's own reds that #1407 fixed after this stack's base.

## Decisions made during this task
DEC-2428
