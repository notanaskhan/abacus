---
id: TASK-8071
title: "C-01-T02 rest: QC-3's staff-only function condition, and the missing A-08 conditions in has_conditions"
spec: SPEC-655
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: c01-t02-staff-function-condition
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T02
---

## Objective
Close C-01-T02's partial (DEC-5002): staff start a close's runs only with `close_preparer` on
that close (QC-3). Partners, managers and seniors start them without that function.

## Plan (red)
- The compiler gets a new condition key, `staff_function_in(...)`. When `staff` is the only role
  that allowed the action, the actor must hold one of the listed functions on the target's work
  item. Any other granting role is unaffected. If the granting roles are unknown, it fails closed.
- In `authorise`, the granting roles reach `ConditionFacts.granting_roles`. The functions lookup
  runs for `staff_function_in` as it does for `function_in`.
- `closes.yaml`: `close_run.start` and `close_run.retry` get `staff: allow,
  staff_function_in: close_preparer`. `_matrix.py` is regenerated.
- Codegen: the generated security suite expects staff denied (the harness holds no work-item
  functions) and the other roles allowed.
- **Found in review:** `has_conditions` did not list A-08-T03's `is_named_approver`,
  `link_scope_only` or `email_verified`. An action whose only condition was one of them skipped the
  check (fail open). All three are listed now, as is `staff_function_in`. A test holds every key the
  parser knows to `has_conditions`.
- Rollback: revert the commit and regenerate. No migration.

## Progress log
- `2026-11-15` — Built (DEC-5057). Lint, pyright, banned_patterns, generator_coverage and
  fresh_mfa are clean; the suites run at the end pass.
