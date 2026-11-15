---
id: TASK-8045
title: "A-08-T03: fieldwork protected bundle (matrix, conditions, link_principal role, flags, control)"
spec: SPEC-657
acceptance_criteria: [AC-0, AC-9]
risk_zone: red
status: in-review
branch: a08-t03-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T03
---

## Objective
The S45 protected bundle every later A-08 row builds on: per-module matrix rows, the conditions
`is_named_approver`, `link_scope_only`, `email_verified`, the six flags and the
`confirmation_links` kill switch.

## Plan (red: written before the build)
1. **Protected** matrix files: `_roles.yaml` (+ `link_principal`), `sampling`, `workpapers`,
   `assurance`, `identity`; `make regenerate` (`_matrix.py`, `actions.gen.ts`, security tests).
2. **Protected** `identity/authz/{matrix,conditions,__init__}.py`: the three conditions, fail closed.
3. `abacus_tools/codegen/security_tests.py`: expected deny without facts; resolution entities.
4. **Protected** flag files (six flags, DEC-137 override).
5. Migration **0887** `confirmation_links` control (expand-only CHECK widen); `kernel/controls.py`,
   `abacus_tools/platform_control.py`.
Rollback: revert; downgrade 0887 drops any `confirmation_links` row.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010); plan above written before building.
- `2026-11-15` — Built (DEC-5030). Codegen clean (permission_matrix, role_templates,
  feature_flags, security_tests); pyright clean on touched files. Tests written
  (`test_a08t03_conditions.py`, regenerated security suites), run at the end pass.
- **Partial:** table registrations, notification kinds, gate subjects and error codes ride the
  rows that create their tables, events and exceptions (DEC-5030).
