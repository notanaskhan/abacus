---
id: TASK-8318
title: "A-09-T21: Component scope in identity and the portal shell"
spec: docs/specs/SPEC-658 F6
acceptance_criteria: [A-09-T21]
risk_zone: red
status: in-review
branch: a09-t21-component-scope
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T21
---

## Objective
Component scope in identity and the portal shell.

## Plan (red)
1. `assurance/component_scope.py`: the `component` scope resolver (registered in `assurance/api.py`), `component_ids` (the person's active component-auditor grants), `require_room` (404 otherwise), `foreign_figures` (a message naming another component's figures).
2. Tests: `tests/unit/assurance/test_a09t21_component_scope.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5314). The app imports; the unit file ran green (2 tests). Partial: the 14-day single-use component invitations with mandatory MFA, `/v1/me`'s component shell and the `/component-room` landing, the communications check wiring and revocation on archive are not built (the room routes in `portal/component_room_contract.py` still answer 501). Gates and
  tests run once at the S47 end pass (build first, test last).
