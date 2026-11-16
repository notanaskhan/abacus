---
id: TASK-8309
title: "A-08-T14: Attribute testing variants je_testing, test_of_details and test_of_controls on A-05's shared grid"
spec: SPEC-657
acceptance_criteria: [AC-2]
risk_zone: amber
status: in-review
branch: a08-t14-attribute-variants
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T14
---

## Objective
Spec section: docs/plan/epics/A-08.md §3 F2.
Attribute testing variants je_testing, test_of_details and test_of_controls on A-05's shared grid.

## Plan (amber)
1. Migration `0930_fieldwork_tests.py` on 0921: `attribute_tests.variant` gains `aud12_je`; insert-only `control_deviations` (tenant RLS, column grants; a below-CT difference can never be an exception, CHECK).
2. `workpapers/compute/attribute_stats.py` (pure): exact one-sided UDL (Clopper-Pearson, Decimal bisection), the clearly-trivial rule.
3. `workpapers/fieldwork_tests.py`: variant tests and the variant swap, `log_deviation` (person only; below CT is a `difference`; an exception may route to `assurance.api.record_finding` in the same act), `deviation_log` with UDL.
4. `workpapers/attribute_grid.py`: the `aud12_je` variant; `workpapers/registry.py`: the new table; audit kind reviewed.
5. Tests: `tests/unit/workpapers/test_a08t14_attribute_stats.py`. Rollback: `alembic downgrade 0921` (drops the log, deletes `aud12_je` tests).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5306). Lint and pyright clean; the unit file ran green (8 tests). Partial: the deterministic JE Testing.xlsx export and the JE item detail's C4 citation reads are not built (the grid's existing citations serve the screen); the L1 adopt is the grid's existing reviewable sign-off. Gates and
  tests run once at the S47 end pass (build first, test last).
