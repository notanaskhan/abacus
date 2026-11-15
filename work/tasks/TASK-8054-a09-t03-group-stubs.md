---
id: TASK-8054
title: "A-09-T03: contract stubs — C9 v2.1 consolidation, C8 v1.1 eliminations, group audit, component room"
spec: SPEC-658
acceptance_criteria: [AC-0.3]
risk_zone: amber
status: in-review
branch: a09-t03-group-stubs
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T03
---

## Objective
Contract first for A-09: classified models, 501 routes under one action each behind
`group_audit`, seed-derived typed fixtures, contract docs, `make generate`.

## Plan (amber: written before the build)
1. `assurance/group_contract.py` (consolidation, eliminations, group audit) and
   `portal/component_room_contract.py`; routers registered; error catalogue; `make generate`.
2. `assurance/group_fixtures.py` (computed footings).
3. `docs/contracts/ledger-consolidation.md`, `group-audit.md`, the C8 v1.1 section of `adjustments.md`.
Rollback: revert; no table, no write.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Built (DEC-5039). ruff, pyright and web tsc clean; footings checked by a one-off
  run. Consumer tests are A-09-T06.
- **Mistake twice:** generic model and handler names collided in the OpenAPI document again
  (A-08-T05 `CoverageOut`; here `list_deliverables`). Candidate lint: unique schema names and
  operation ids across modules, checked in `make generate`.
