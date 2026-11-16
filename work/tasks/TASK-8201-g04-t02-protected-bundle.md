---
id: TASK-8201
title: "G-04-T02: protected bundle — platform firm and staff matrix sections, three flags, DF-31 status rows, glossary"
spec: SPEC-680
acceptance_criteria: [AC-30, AC-41]
risk_zone: red
status: in-review
branch: g04-t02-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-15
updated: 2026-11-15
plan_key: G-04-T02
---

## Objective
The bundle every G-04 row builds on, with both founders' approval in the plan.

## Plan (red)
1. **Protected** `permission-matrix/_roles.yaml` (+ `platform_admin`, `platform_support_desk`),
   `platform.yaml` (8 firm, 8 staff actions), `identity.yaml` (`support_session.decline`).
2. **Protected** `identity/authz/overrides.py`: the staff roles join `PLATFORM_ROLES`.
3. **Protected** `feature-flags/platform.yaml` (three flags).
4. **Protected** `status-vocabulary.yaml`, `glossary.md`.
5. `make regenerate`; `tests/security/test_g04_matrix_denials.py`.
Rollback: revert (no route uses the new actions until T03).

## Progress log
- `2026-11-15` — Built (DEC-5202). Codegen clean. The epic's `platform.x.y` actions renamed to
  `platform_x.y` (the matrix's `entity.verb` rule). Generated matrix tests and the new denial
  test run at the lane's end pass. **Needs:** both founders' approval (the plan); Ayush approves.
